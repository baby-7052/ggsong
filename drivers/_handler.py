"""
Main bot handler with Telegram operations
"""
import re
import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timezone
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait, ChatWriteForbidden, MediaEmpty, 
    FileReferenceExpired, UserNotParticipant, RPCError
)
from _config import Config
from _manager import FileManager
from _cache import CacheManager

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.app = Client(
            "spacefx",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN
        )
        
        self.file_manager = FileManager(Config.DOWNLOADS_DIR)
        self.cache_manager = CacheManager(Config.CACHE_FILE)
        self.is_running = False
        self.current_interval = Config.DEFAULT_INTERVAL
        self.forwarding_task: Optional[asyncio.Task] = None
        self.stats = {
            'files_forwarded': 0,
            'files_skipped': 0,
            'errors': 0,
            'started_at': None
        }
        
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup message handlers"""
        @self.app.on_message(filters.command("start") & filters.private)
        async def start_command(client: Client, message: Message):
            logger.info(f"User {message.from_user.id} sent /start")
            if not self.is_authorized_user(message.from_user.id):
                await message.reply("❌ You are not authorized to use this bot.")
                return
            await message.reply(
                "🤖 **Telegram Auto Forwarder Bot**\n\n"
                "📁 **Commands:**\n"
                "• `/start` - Show this message\n"
                "• `/status` - Show bot status\n"
                "• `/run` - Start auto forwarding\n"
                "• `/stop` - Stop auto forwarding\n"
                "• `/interval <seconds>` - Set forwarding interval\n"
                "• `/stats` - Show statistics\n"
                "• `/files` - List pending files\n"
                "• `/cleanup` - Clean old cache entries\n"
                "• `/test` - Test target chat connection\n\n"
                f"📂 **Monitoring:** `{Config.DOWNLOADS_DIR}`\n"
                f"📤 **Target:** `{Config.TARGET_CHAT_ID}`\n"
                f"⏱️ **Current Interval:** {self.current_interval}s"
            )
        
        @self.app.on_message(filters.command("status") & filters.private)
        async def status_command(client: Client, message: Message):
            if not self.is_authorized_user(message.from_user.id):
                return
            
            status = "🟢 Running" if self.is_running else "🔴 Stopped"
            uptime = ""
            
            if self.stats['started_at']:
                uptime_seconds = (datetime.now(timezone.utc) - self.stats['started_at']).total_seconds()
                hours, remainder = divmod(uptime_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime = f"\n⏰ **Uptime:** {int(hours)}h {int(minutes)}m {int(seconds)}s"
            
            await message.reply(
                f"📊 **Bot Status**\n\n"
                f"🔄 **Status:** {status}\n"
                f"⏱️ **Interval:** {self.current_interval}s\n"
                f"📁 **Downloads Dir:** `{Config.DOWNLOADS_DIR}`\n"
                f"📤 **Target Chat:** `{Config.TARGET_CHAT_ID}`"
                f"{uptime}"
            )
        
        @self.app.on_message(filters.command("test") & filters.private)
        async def test_command(client: Client, message: Message):
            """Test target chat connection"""
            if not self.is_authorized_user(message.from_user.id):
                return
            await message.reply("🧪 Testing target chat connection...")
            success = await self.test_target_chat(send_message=True)
            if success:
                await message.reply("✅ Target chat test successful! Bot can send messages.")
            else:
                await message.reply("❌ Target chat test failed! Check logs for details.")
        
        @self.app.on_message(filters.command("run") & filters.private)
        async def run_command(client: Client, message: Message):
            if not self.is_authorized_user(message.from_user.id):
                return
            if self.is_running:
                await message.reply("⚠️ Bot is already running!")
                return
            await message.reply("🧪 Verifying target chat access...")
            if not await self.test_target_chat(send_message=False):
                await message.reply(
                    "❌ Cannot access target chat!\n\n"
                    "**Possible issues:**\n"
                    "• Invalid TARGET_CHAT_ID\n"
                    "• Bot not added to target channel/group\n"
                    "• Bot lacks permission to send messages\n\n"
                    "Use `/test` command to debug the issue."
                )
                return
            await self.start_forwarding()
            await message.reply("✅ Auto forwarding started!")
        
        @self.app.on_message(filters.command("stop") & filters.private)
        async def stop_command(client: Client, message: Message):
            if not self.is_authorized_user(message.from_user.id):
                return
            if not self.is_running:
                await message.reply("⚠️ Bot is not running!")
                return
            await self.stop_forwarding()
            await message.reply("🛑 Auto forwarding stopped!")
        
        @self.app.on_message(filters.command("interval") & filters.private)
        async def interval_command(client: Client, message: Message):
            if not self.is_authorized_user(message.from_user.id):
                return
            try:
                args = message.text.split()
                if len(args) != 2:
                    await message.reply("❌ Usage: `/interval <seconds>`\nExample: `/interval 120`")
                    return
                new_interval = int(args[1])
                if new_interval < 10:
                    await message.reply("❌ Minimum interval is 10 seconds")
                    return
                self.current_interval = new_interval
                await message.reply(f"✅ Interval updated to {new_interval} seconds")
            except ValueError:
                await message.reply("❌ Invalid interval. Please provide a number in seconds.")
        
        @self.app.on_message(filters.command("stats") & filters.private)
        async def stats_command(client: Client, message: Message):
            if not self.is_authorized_user(message.from_user.id):
                return
            forwarded_count = await self.cache_manager.get_forwarded_files_count()
            await message.reply(
                f"📈 **Statistics**\n\n"
                f"📤 **Files Forwarded:** {self.stats['files_forwarded']}\n"
                f"⏭️ **Files Skipped:** {self.stats['files_skipped']}\n"
                f"❌ **Errors:** {self.stats['errors']}\n"
                f"💾 **Total in Cache:** {forwarded_count}\n"
                f"📁 **Downloads Dir:** `{Config.DOWNLOADS_DIR}`"
            )
        
        @self.app.on_message(filters.command("files") & filters.private)
        async def files_command(client: Client, message: Message):
            if not self.is_authorized_user(message.from_user.id):
                return
            files = self.file_manager.get_all_files()
            pending_files = []
            for file_path in files[:10]:  # Show max 10 files
                if not await self.cache_manager.is_file_forwarded(str(file_path)):
                    file_info = self.file_manager.get_file_info(file_path)
                    pending_files.append(f"📄 `{file_info['name']}` ({file_info['size_mb']} MB)")
            if pending_files:
                files_text = "\n".join(pending_files)
                more_text = f"\n\n... and {len(files) - len(pending_files)} more files" if len(files) > 10 else ""
                await message.reply(f"📋 **Pending Files:**\n\n{files_text}{more_text}")
            else:
                await message.reply("✅ No pending files to forward!")
        
        @self.app.on_message(filters.command("cleanup") & filters.private)
        async def cleanup_command(client: Client, message: Message):
            if not self.is_authorized_user(message.from_user.id):
                return
            cleaned = await self.cache_manager.cleanup_old_entries(days=30)
            await message.reply(f"🧹 Cleaned up {cleaned} old cache entries (older than 30 days)")
    
    def is_authorized_user(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return user_id in Config.AUTHORIZED_USERS
    
    async def test_target_chat(self, send_message: bool = False) -> bool:
        """Test if target chat is accessible. Only sends a visible test message when send_message=True."""
        try:
            chat = await self.app.get_chat(Config.TARGET_CHAT_ID)
            logger.info(f"Target chat found: {chat.title} (ID: {chat.id}, Type: {chat.type})")
            if send_message:
                test_message = await self.app.send_message(
                    Config.TARGET_CHAT_ID, 
                    "🧪 **Test Message**\n\nBot connection with database & channel successful! This message will be deleted in 5 seconds."
                )
                logger.info(f"Test message sent successfully: {test_message.id}")
                await asyncio.sleep(5)
                try:
                    await self.app.delete_messages(Config.TARGET_CHAT_ID, test_message.id)
                    logger.info("Test message deleted successfully")
                except Exception as e:
                    logger.warning(f"Could not delete test message: {e}")
            return True
        except Exception as e:
            logger.error(f"Target chat test failed: {e}")
            return False
    
    async def start_forwarding(self):
        """Start the auto forwarding process"""
        if self.is_running:
            return
        self.is_running = True
        self.stats['started_at'] = datetime.now(timezone.utc)
        self.file_manager.ensure_downloads_dir()
        await self.cache_manager.load_cache()
        self.forwarding_task = asyncio.create_task(self._forwarding_loop())
        logger.info("Auto forwarding started")
    
    async def stop_forwarding(self):
        """Stop the auto forwarding process"""
        if not self.is_running:
            return
        self.is_running = False
        if self.forwarding_task:
            self.forwarding_task.cancel()
            try:
                await self.forwarding_task
            except asyncio.CancelledError:
                pass
        logger.info("Auto forwarding stopped")
    
    async def _forwarding_loop(self):
        """Main forwarding loop"""
        while self.is_running:
            try:
                await self._process_files()
                await asyncio.sleep(self.current_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in forwarding loop: {e}")
                self.stats['errors'] += 1
                await asyncio.sleep(min(self.current_interval, 60))
    
    async def _process_files(self):
        """Process and forward files"""
        files = self.file_manager.get_all_files()
        
        for file_path in files:
            if not self.is_running:
                break
            try:
                if await self.cache_manager.is_file_forwarded(str(file_path)):
                    continue
                if not self.file_manager.is_file_accessible(file_path):
                    logger.warning(f"File not accessible: {file_path.name}")
                    continue
                if not await self.file_manager.wait_for_file_stability(file_path, timeout=10):
                    logger.warning(f"File not stable: {file_path.name}")
                    continue
                file_info = self.file_manager.get_file_info(file_path)
                if file_info['size_mb'] > Config.MAX_FILE_SIZE_MB:
                    logger.warning(f"File too large: {file_path.name} ({file_info['size_mb']} MB)")
                    await self.cache_manager.mark_file_forwarded(str(file_path))
                    self.stats['files_skipped'] += 1
                    continue
                success = await self._forward_file(file_path, file_info)
                if success:
                    self.stats['files_forwarded'] += 1
                    logger.info(f"Successfully forwarded: {file_path.name}")
                else:
                    self.stats['errors'] += 1
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing file {file_path.name}: {e}")
                self.stats['errors'] += 1
    
    async def _forward_file(self, file_path: Path, file_info: dict, retry_count: int = 0) -> bool:
        """Forward a single file with error handling"""
        try:
            if file_info['mime_type'].startswith('image/'):
                message = await self.app.send_photo(
                    chat_id=Config.TARGET_CHAT_ID,
                    photo=str(file_path),
                    caption=f"📸 {file_info['name']}\n💾 Size: {file_info['size_mb']} MB"
                )
            elif file_info['mime_type'].startswith('video/'):
                message = await self.app.send_video(
                    chat_id=Config.TARGET_CHAT_ID,
                    video=str(file_path),
                    caption=f"🎥 {file_info['name']}\n💾 Size: {file_info['size_mb']} MB"
                )
            elif file_info['mime_type'].startswith('audio/'):
                message = await self.app.send_audio(
                    chat_id=Config.TARGET_CHAT_ID,
                    audio=str(file_path),
                    caption=f"🎵 {file_info['name']}\n💾 Size: {file_info['size_mb']} MB"
                )
            else:
                message = await self.app.send_document(
                    chat_id=Config.TARGET_CHAT_ID,
                    document=str(file_path),
                    caption=f"📄 {file_info['name']}\n💾 Size: {file_info['size_mb']} MB"
                )
            await self.cache_manager.mark_file_forwarded(str(file_path), message.id)
            return True
            
        except FloodWait as e:
            logger.warning(f"FloodWait: {e.value} seconds for {file_path.name}")
            await asyncio.sleep(e.value + 1)
            if retry_count < Config.MAX_RETRY_ATTEMPTS:
                return await self._forward_file(file_path, file_info, retry_count + 1)
            return False
        except (ChatWriteForbidden, UserNotParticipant) as e:
            logger.error(f"Permission error: {e}")
            return False
        except (MediaEmpty, FileReferenceExpired) as e:
            logger.error(f"Media error for {file_path.name}: {e}")
            return False
            
        except RPCError as e:
            error_message = str(e)
            if "SLOWMODE_WAIT" in error_message:
                wait_match = re.search(r'SLOWMODE_WAIT_(\d+)', error_message)
                wait_time = int(wait_match.group(1)) if wait_match else 60
                
                logger.warning(f"Slow mode wait: {wait_time} seconds for {file_path.name}")
                await asyncio.sleep(wait_time + 1)
                
                if retry_count < Config.MAX_RETRY_ATTEMPTS:
                    return await self._forward_file(file_path, file_info, retry_count + 1)
                return False
            elif "PEER_ID_INVALID" in error_message:
                logger.error(f"Invalid target chat ID: {Config.TARGET_CHAT_ID}")
                return False
            else:
                logger.error(f"RPC error for {file_path.name}: {e}")
                if retry_count < Config.MAX_RETRY_ATTEMPTS:
                    await asyncio.sleep(5 * (retry_count + 1))
                    return await self._forward_file(file_path, file_info, retry_count + 1)
                return False
            
        except Exception as e:
            logger.error(f"Unexpected error forwarding {file_path.name}: {e}")
            
            if retry_count < Config.MAX_RETRY_ATTEMPTS:
                await asyncio.sleep(5 * (retry_count + 1))  # Exponential backoff
                return await self._forward_file(file_path, file_info, retry_count + 1)
            return False

    async def run(self):
        """Run the bot"""
        logger.info("Starting Telegram Auto Forwarder Bot...")
        if not Config.validate():
            logger.error("Invalid configuration. Please check your environment variables.")
            return
        logger.info(f"Configuration Debug:")
        logger.info(f"TARGET_CHAT_ID: {Config.TARGET_CHAT_ID}")
        logger.info(f"AUTHORIZED_USERS: {Config.AUTHORIZED_USERS}")
        logger.info(f"DOWNLOADS_DIR: {Config.DOWNLOADS_DIR}")
        
        try:
            await self.app.start()
            logger.info("Bot started successfully!")
            logger.info("Verifying target chat accessibility...")
            if await self.test_target_chat(send_message=False):
                logger.info("✅ Target chat verified!")
            else:
                logger.error("❌ Target chat test failed! Check TARGET_CHAT_ID and bot permissions.")
            
            if Config.AUTHORIZED_USERS:
                for user_id in Config.AUTHORIZED_USERS:
                    try:
                        await self.app.send_message(
                            user_id,
                            "🤖 **Auto Forwarder Bot Started!**\n\n"
                            f"📂 Monitoring: `{Config.DOWNLOADS_DIR}`\n"
                            f"📤 Target: `{Config.TARGET_CHAT_ID}`\n"
                            f"⏱️ Interval: {Config.DEFAULT_INTERVAL}s\n\n"
                            "Use `/run` to start auto forwarding!\n"
                            "Use `/test` to verify target chat connection."
                        )
                        logger.info(f"Startup notification sent to user {user_id}")
                        break
                    except Exception as e:
                        logger.warning(f"Could not send startup message to {user_id}: {e}")
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self.stop_forwarding()
            await self.app.stop()
