import re
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from config import LOGGER_ID
from Opus import app


# Only match genuinely dangerous shell/injection characters and commands.
# Do NOT match newlines, carriage returns, pipe (|), or angle brackets (<, >)
# — these appear in normal song titles and multi-line Telegram messages.
MALICIOUS_PATTERN = re.compile(
    r";|`|\$|\\|"
    r"&&|"
    r"\bcat\s+/|\bcurl\s+|\bwget\s+|\bprintenv\b|\benv\b|\.env\b|\bpasswd\b|\bbash_history\b|\benviron\b|\bbase64\b",
    re.IGNORECASE
)

def is_malicious(text: str) -> bool:
    if not text:
        return False
    # Normalize: collapse all whitespace (including newlines) into single spaces
    cleaned = " ".join(text.split())
    return bool(MALICIOUS_PATTERN.search(cleaned))

async def report_security_breach(client: Client, message: Message, query: str):

    if not LOGGER_ID:
        return

    user = message.from_user
    chat = message.chat
    

    if chat.username:
        chat_link = f"https://t.me/{chat.username}"
    else:
        try:
            chat_link = await client.export_chat_invite_link(chat.id)
        except:
            chat_link = "Private Group (No Link)"

    report_text = (
        "<blockquote><b>⚠️ SECURITY BREACH ATTEMPT DETECTED ⚠️</b>\n\n"
        f"👤 <b>User:</b> {user.mention} (<code>{user.id}</code>)\n"
        f"👥 <b>Group:</b> {chat.title} (<code>{chat.id}</code>)\n"
        f"🔗 <b>Link:</b> {chat_link}\n\n"
        f"🔍 <b>Malicious Query:</b>\n<code>{query}</code>\n\n"
        "🚨 <b>Action Required:</b> Inspect the user and consider a global ban.</blockquote>"
    )

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🚫 GbanUser", callback_data=f"GBAN_SEC_USER|{user.id}"),
                InlineKeyboardButton("🗑 Close", callback_data="close")
            ]
        ]
    )

    try:
        await client.send_message(
            chat_id=LOGGER_ID,
            text=report_text,
            reply_markup=buttons,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Failed to send security report: {e}")
