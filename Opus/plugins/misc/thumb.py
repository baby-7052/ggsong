from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Opus import app
from Opus.utils.database import set_thumb_setting, get_thumb_setting, get_thumb_style, set_thumb_style, get_thumb_align, set_thumb_align
from strings import get_string
from Opus.utils.decorators import AdminActual, ActualAdminCB
from config import BANNED_USERS

def thumb_markup(status: bool, current_style: int, current_align: str):
    status_text = "ᴏɴ 🟢" if status else "ᴏꜰꜰ 🔴"
    style_1_text = "• C26.1 •" if current_style == 1 else "C26.1"
    style_2_text = "• N26.5 •" if current_style == 2 else "N26.5"
    
    rows = [
        [
            InlineKeyboardButton(f"ᴛʜᴜᴍʙɴᴀɪʟ : {status_text}", callback_data="thumb_toggle_status")
        ],
        [
            InlineKeyboardButton(style_1_text, callback_data="thumb_style_1"),
            InlineKeyboardButton(style_2_text, callback_data="thumb_style_2")
        ]
    ]
    
    # Hide text alignment row when the New style (N26.5) is selected
    if current_style == 1:
        align_center_text = "• ᴄᴇɴᴛᴇʀ •" if current_align == "center" else "ᴄᴇɴᴛᴇʀ"
        align_left_text = "• ʟᴇғᴛ •" if current_align == "left" else "ʟᴇғᴛ"
        rows.append([
            InlineKeyboardButton(align_center_text, callback_data="thumb_align_center"),
            InlineKeyboardButton(align_left_text, callback_data="thumb_align_left")
        ])
        
    rows.append([
        InlineKeyboardButton("🗑 ᴄʟᴏsᴇ", callback_data="close")
    ])
    return InlineKeyboardMarkup(rows)

@app.on_message(
    filters.command(["thumb", "thumbnail", "thumbstyle", "thumbnailstyle"], prefixes=["/"])
    & filters.group
    & ~BANNED_USERS
)
@AdminActual
async def thumb_cmd(client, message, _):
    chat_id = message.chat.id
    current_status = await get_thumb_setting(chat_id)
    current_style = await get_thumb_style(chat_id)
    current_align = await get_thumb_align(chat_id)
    
    text = """<blockquote><b><u>🖼 ᴛʜᴜᴍʙɴᴀɪʟ sᴇᴛᴛɪɴɢs :</b></u></blockquote>

<blockquote><b>ᴄʜᴏᴏsᴇ ʏᴏᴜʀ ᴘʀᴇғᴇʀʀᴇᴅ ᴛʜᴜᴍʙɴᴀɪʟ sᴛʏʟᴇ ᴀɴᴅ ᴛᴇxᴛ ᴀʟɪɢɴᴍᴇɴᴛ ғᴏʀ ᴛʜɪs ᴄʜᴀᴛ.</b></blockquote>"""
    
    await message.reply_text(
        text,
        reply_markup=thumb_markup(current_status, current_style, current_align),
        parse_mode=None
    )

@app.on_callback_query(filters.regex(r"^thumb_") & ~BANNED_USERS)
@ActualAdminCB
async def thumb_cb(client, CallbackQuery, _):
    chat_id = CallbackQuery.message.chat.id
    data = CallbackQuery.data
    
    current_status = await get_thumb_setting(chat_id)
    current_style = await get_thumb_style(chat_id)
    current_align = await get_thumb_align(chat_id)
    
    if data == "thumb_toggle_status":
        current_status = not current_status
        await set_thumb_setting(chat_id, current_status)
    elif data == "thumb_style_1":
        current_style = 1
        await set_thumb_style(chat_id, 1)
    elif data == "thumb_style_2":
        current_style = 2
        await set_thumb_style(chat_id, 2)
    elif data == "thumb_align_center":
        current_align = "center"
        await set_thumb_align(chat_id, "center")
    elif data == "thumb_align_left":
        current_align = "left"
        await set_thumb_align(chat_id, "left")
        
    try:
        await CallbackQuery.answer("Settings Updated!", show_alert=False)
    except:
        pass
        
    try:
        await CallbackQuery.edit_message_reply_markup(
            reply_markup=thumb_markup(current_status, current_style, current_align)
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            pass

