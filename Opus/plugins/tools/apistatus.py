import time
import asyncio
from datetime import datetime
import httpx
import psutil

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from Opus import app
from Opus.core.call import Signal
from Opus.utils import bot_sys_stats
from Opus.misc import SUDOERS
from Opus.utils.api_logs import get_logs_file, _logs
from config import BANNED_USERS, OWNER_ID
import config

async def probe_api(url: str, timeout: int = 5) -> str:
    try:
        start_time = time.time()
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            duration = int((time.time() - start_time) * 1000)
            if resp.status_code in (200, 400, 405):
                return f"🟢 ᴏɴʟɪɴᴇ ({duration}ms)"
            return f"🟡 ᴇʀʀᴏʀ ({resp.status_code})"
    except Exception:
        return "🔴 ᴏғғʟɪɴᴇ"

async def get_apistatus_text(start_time) -> tuple:
    # Gather system and call stats
    pytgping = "Unknown"
    try:
        pytgping = await Signal.ping()
    except Exception:
        pass

    stats = await bot_sys_stats()
    UP, CPU, RAM, DISK = stats
    resp = (datetime.now() - start_time).microseconds / 10000

    # Probe external APIs concurrently without exposing plain URLs in source code
    synczen_url = f"{config.SYNCZEN_API_URL}?q=test" if config.SYNCZEN_API_URL else ""
    synczen_task = asyncio.create_task(probe_api(synczen_url)) if synczen_url else None
    honox_task = asyncio.create_task(probe_api(config.HONOX_API_URL)) if config.HONOX_API_URL else None
    cobalt_task = asyncio.create_task(probe_api(config.COBALT_API_URL)) if config.COBALT_API_URL else None

    synczen_status = await synczen_task if synczen_task else "🔴 ᴏғғʟɪɴᴇ"
    honox_status = await honox_task if honox_task else "🔴 ᴏғғʟɪɴᴇ"
    cobalt_status = await cobalt_task if cobalt_task else "🔴 ᴏғғʟɪɴᴇ"

    text = (
        f"<blockquote>📊 <b>﹝  ᴀᴘɪ & sʏsᴛᴇᴍ sᴛᴀᴛᴜs  ﹞</b>\n\n"
        f"🤖 <b>ʙᴏᴛ ᴘɪɴɢ:</b> {resp:.1f} ms\n"
        f"📞 <b>ᴘʏᴛɢᴄᴀʟʟs ᴘɪɴɢ:</b> {pytgping} ms\n"
        f"📶 <b>sʏsᴛᴇᴍ ᴜᴘᴛɪᴍᴇ:</b> {UP}\n\n"
        f"🔌 <b>ᴀᴘɪ ʜᴇᴀʟᴛʜ sᴛᴀᴛᴜs:</b>\n"
        f"● <b>ᴀᴘɪ sᴇʀᴠᴇʀ 1:</b> {synczen_status}\n"
        f"● <b>ᴀᴘɪ sᴇʀᴠᴇʀ 2:</b> {honox_status}\n"
        f"● <b>ᴀᴘɪ sᴇʀᴠᴇʀ 3:</b> {cobalt_status}\n\n"
        f"💻 <b>sʏsᴛᴇᴍ ʀᴇsᴏᴜʀᴄᴇs:</b>\n"
        f"● <b>ᴄᴘᴜ:</b> {CPU}\n"
        f"● <b>ʀᴀᴍ:</b> {RAM}\n"
        f"● <b>ᴅɪsᴋ:</b> {DISK}</blockquote>"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📥 ɢᴇᴛ ʟᴏɢs", callback_data="get_api_logs"),
                InlineKeyboardButton("🔄 ʀᴇғʀᴇsʜ", callback_data="refresh_api_status"),
            ],
            [
                InlineKeyboardButton("🗑️ ᴄʟᴇᴀʀ ʟᴏɢs", callback_data="clear_api_logs")
            ]
        ]
    )

    return text, keyboard

@app.on_message(filters.command(["apistatus", "apisatus", "apistats"]) & ~BANNED_USERS)
async def apistatus_cmd(client, message: Message):
    if message.from_user.id not in SUDOERS and message.from_user.id != OWNER_ID:
        return await message.reply_text("🚫 ᴏɴʟʏ sᴜᴅᴏ ᴜsᴇʀs ᴏʀ ᴛʜᴇ ᴏᴡɴᴇʀ ᴄᴀɴ ᴠɪᴇᴡ ᴀᴘɪ sᴛᴀᴛᴜs.")

    mystic = await message.reply_text("📊 ғᴇᴛᴄʜɪɴɢ ᴀᴘɪ ᴀɴᴅ sʏsᴛᴇᴍ sᴛᴀᴛᴜs...")
    start_time = datetime.now()
    text, keyboard = await get_apistatus_text(start_time)
    await mystic.edit_text(text, reply_markup=keyboard)

@app.on_callback_query(filters.regex("get_api_logs") & ~BANNED_USERS)
async def get_api_logs_cb(client, CallbackQuery: CallbackQuery):
    if CallbackQuery.from_user.id not in SUDOERS and CallbackQuery.from_user.id != OWNER_ID:
        return await CallbackQuery.answer("🚫 ᴏɴʟʏ sᴜᴅᴏ ᴜsᴇʀs ᴏʀ ᴛʜᴇ ᴏᴡɴᴇʀ ᴄᴀɴ ᴀᴄᴄᴇss ʟᴏɢs.", show_alert=True)

    await CallbackQuery.answer("Sending logs.txt... 📤")
    bio = get_logs_file()
    await CallbackQuery.message.reply_document(
        document=bio,
        file_name="api_logs.txt",
        caption="📂 <b>﹝  ᴀᴘɪ sᴛᴀᴛᴜs ʟᴏɢs  ﹞</b>"
    )

@app.on_callback_query(filters.regex("refresh_api_status") & ~BANNED_USERS)
async def refresh_api_status_cb(client, CallbackQuery: CallbackQuery):
    if CallbackQuery.from_user.id not in SUDOERS and CallbackQuery.from_user.id != OWNER_ID:
        return await CallbackQuery.answer("🚫 ᴏɴʟʏ sᴜᴅᴏ ᴜsᴇʀs ᴏʀ ᴛʜᴇ ᴏᴡɴᴇʀ ᴄᴀɴ ʀᴇғʀᴇsʜ sᴛᴀᴛᴜs.", show_alert=True)

    await CallbackQuery.answer("Refreshing stats... 🔄")
    start_time = datetime.now()
    text, keyboard = await get_apistatus_text(start_time)
    await CallbackQuery.edit_message_text(text, reply_markup=keyboard)

@app.on_callback_query(filters.regex("clear_api_logs") & ~BANNED_USERS)
async def clear_api_logs_cb(client, CallbackQuery: CallbackQuery):
    if CallbackQuery.from_user.id not in SUDOERS and CallbackQuery.from_user.id != OWNER_ID:
        return await CallbackQuery.answer("🚫 ᴏɴʟʏ sᴜᴅᴏ ᴜsᴇʀs ᴏʀ ᴛʜᴇ ᴏᴡɴᴇʀ ᴄᴀɴ ᴄʟᴇᴀʀ ʟᴏɢs.", show_alert=True)

    _logs.clear()
    await CallbackQuery.answer("Logs cleared successfully! 🗑️", show_alert=True)
