"""
Main entry point for Telegram Auto Forwarder Bot
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

from _handler import TelegramBot
from _config import Config
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main function with singleton check"""
    pid_file = Path(__file__).parent / "driver.pid"
    
    # Singleton check
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            os.kill(old_pid, 0) # Check if process exists
            logger.error(f"❌ Driver is already running with PID {old_pid}. Exiting.")
            return
        except (ProcessLookupError, ValueError, OSError):
            # Process is dead but PID file remains
            pid_file.unlink()

    # Create PID file
    pid_file.write_text(str(os.getpid()))

    try:
        if not Config.validate():
            logger.error(
                "❌ Invalid configuration!\n"
                "Please set the following environment variables:\n"
                "- API_ID: Your Telegram API ID\n"
                "- API_HASH: Your Telegram API Hash\n"
                "- BOT_TOKEN: Your Bot Token from @BotFather\n"
                "- TARGET_CHAT_ID: Target channel/group ID or Username(e.g., -1001234567890)\n"
                "- AUTHORIZED_USERS: Comma-separated user IDs (e.g., 123456789,987654321)"
            )
            return
        bot = TelegramBot()
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        if pid_file.exists():
            pid_file.unlink()

if __name__ == "__main__":
    # Ensure Python 3.8+
    if sys.version_info < (3, 8):
        print("Python 3.8 or higher is required!")
        sys.exit(1)
    asyncio.run(main())
