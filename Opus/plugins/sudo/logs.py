import os
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from Opus import app
from Opus.misc import SUDOERS

def smallcaps(text: str) -> str:
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    small = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    return text.translate(str.maketrans(normal, small))

@app.on_message(filters.command(["logs"]) & SUDOERS)
async def fetch_logs_cmd(client, message):
    buttons = [
        [InlineKeyboardButton(f"📄 {smallcaps('Core Logs')} (log.txt)", callback_data="get_log_core")],
        [InlineKeyboardButton(f"🌐 {smallcaps('API Logs')} (api.txt)", callback_data="get_log_api")],
        [InlineKeyboardButton(f"🤖 {smallcaps('Bot Logs')} (bot.log)", callback_data="get_log_bot")],
        [InlineKeyboardButton(f"🔄 {smallcaps('Reboot Logs')} (reboot.txt)", callback_data="get_log_reboot")],
    ]
    from pyrogram.enums import ParseMode
    
    text = (
        f"<b>{smallcaps('SYSTEM LOGS TERMINAL')}</b>\n"
        f"<blockquote>{smallcaps('Select a log file below to download it securely from the server. These logs are isolated to the current deployment and reset on every restart.')}</blockquote>"
    )
    
    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query(filters.regex("^get_log_") & SUDOERS)
async def get_log_cb(client, CallbackQuery: CallbackQuery):
    log_type = CallbackQuery.data.split("_")[2]
    
    file_map = {
        "core": "logs/log.txt",
        "api": "logs/api.txt",
        "bot": "logs/bot.log",
        "reboot": "logs/reboot.txt"
    }
    
    file_path = file_map.get(log_type)
    
    if not file_path or not os.path.exists(file_path):
        return await CallbackQuery.answer("⚠️ Log file does not exist or is empty.", show_alert=True)
        
    from pyrogram.enums import ParseMode
    
    await CallbackQuery.answer(smallcaps("Uploading log file..."))
    try:
        await CallbackQuery.message.reply_document(
            document=file_path, 
            caption=f"<b>{smallcaps(log_type.upper() + ' LOGS')}</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await CallbackQuery.message.reply_text(
            f"<b>{smallcaps('Error uploading')} {smallcaps(log_type)} {smallcaps('logs')}:</b> <code>{e}</code>",
            parse_mode=ParseMode.HTML
        )
