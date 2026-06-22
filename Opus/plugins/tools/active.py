from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from unidecode import unidecode
import unicodedata

from Opus import app
from Opus.misc import SUDOERS
from Opus.utils.database import (
    get_active_chats,
    get_active_video_chats,
    remove_active_chat,
    remove_active_video_chat,
)


async def sync_active_chats():
    """Prunes any stale, dead, or dummy VC sessions from the database memory lists in real-time by querying live PyTgCalls states."""
    try:
        from Opus.core.call import Signal
        from Opus.utils.database import active, activevideo
        
        # Gather all actual group call chat IDs currently active in PyTgCalls across assistants
        actual_chats = set()
        for client in [Signal.one, Signal.two, Signal.three, Signal.four, Signal.five]:
            try:
                for call in client.active_calls:
                    actual_chats.add(call.chat_id)
            except:
                pass
                
        # Instantly prune any inactive chat IDs from memory database lists
        for x in list(active):
            if x not in actual_chats:
                try:
                    active.remove(x)
                except:
                    pass
                    
        for x in list(activevideo):
            if x not in actual_chats:
                try:
                    activevideo.remove(x)
                except:
                    pass
    except Exception as e:
        print(f"Error syncing active chats: {e}")


async def generate_join_link(chat_id: int):
    invite_link = await app.export_chat_invite_link(chat_id)
    return invite_link


def ordinal(n):
    suffix = ["th", "st", "nd", "rd", "th"][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    return str(n) + suffix


@app.on_message(
    filters.command(
        ["activevc", "activevoice"], prefixes=["/"]
    )
    & SUDOERS
)
async def activevc(_, message: Message):
    mystic = await message.reply_text("⌛️")
    
    # Prune and sync before generating the list
    await sync_active_chats()
    
    served_chats = await get_active_chats()
    text = ""
    j = 0
    buttons = []
    for x in served_chats:
        try:
            chat_info = await app.get_chat(x)
            title = chat_info.title
            invite_link = await generate_join_link(x)
        except:
            await remove_active_chat(x)
            continue
        try:
            if chat_info.username:
                user = chat_info.username
                text += f"<blockquote><b>{j + 1}.</b> <a href=https://t.me/{user}>{unidecode(unicodedata.normalize('NFKD', title)).upper()}</a> [<code>{x}</code>]</blockquote>\n"
            else:
                text += (
                    f"<blockquote><b>{j + 1}.</b> {unidecode(unicodedata.normalize('NFKD', title)).upper()} [<code>{x}</code>]</blockquote>\n"
                )
            button_text = f"๏ ᴊᴏɪɴ {ordinal(j + 1)} ɢʀᴏᴜᴘ ๏"
            buttons.append([InlineKeyboardButton(button_text, url=invite_link)])
            j += 1
        except:
            continue
    if not text:
        await mystic.edit_text(f"» ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs ᴏɴ {app.mention}.")
    else:
        await mystic.edit_text(
            f"<blockquote><b>» ʟɪsᴛ ᴏғ ᴄᴜʀʀᴇɴᴛʟʏ ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs :</b></blockquote>\n\n{text}",
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True,
        )


@app.on_message(
    filters.command(
        ["activev", "activevideo"], prefixes=["/"]
    )
    & SUDOERS
)
async def activevi_(_, message: Message):
    mystic = await message.reply_text("⌛️")
    
    # Prune and sync before generating the list
    await sync_active_chats()
    
    served_chats = await get_active_video_chats()
    text = ""
    j = 0
    buttons = []
    for x in served_chats:
        try:
            chat_info = await app.get_chat(x)
            title = chat_info.title
            invite_link = await generate_join_link(x)
        except:
            await remove_active_video_chat(x)
            continue
        try:
            if chat_info.username:
                user = chat_info.username
                text += f"<blockquote><b>{j + 1}.</b> <a href=https://t.me/{user}>{unidecode(unicodedata.normalize('NFKD', title)).upper()}</a> [<code>{x}</code>]</blockquote>\n"
            else:
                text += (
                    f"<blockquote><b>{j + 1}.</b> {unidecode(unicodedata.normalize('NFKD', title)).upper()} [<code>{x}</code>]</blockquote>\n"
                )
            button_text = f"๏ ᴊᴏɪɴ {ordinal(j + 1)} ɢʀᴏᴜᴘ ๏"
            buttons.append([InlineKeyboardButton(button_text, url=invite_link)])
            j += 1
        except:
            continue
    if not text:
        await mystic.edit_text(f"» ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛs ᴏɴ {app.mention}.")
    else:
        await mystic.edit_text(
            f"<blockquote><b>» ʟɪsᴛ ᴏғ ᴄᴜʀʀᴇɴᴛʟʏ ᴀᴄᴛɪᴠᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛs :</b></blockquote>\n\n{text}",
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True,
        )


@app.on_message(filters.command(["ac"]) & SUDOERS)
async def start(client: Client, message: Message):
    # Prune and sync before generating the counts
    await sync_active_chats()
    
    ac_audio = str(len(await get_active_chats()))
    ac_video = str(len(await get_active_video_chats()))
    await message.reply_text(
        f"<blockquote><b><u>ᴀᴄᴛɪᴠᴇ ᴄʜᴀᴛs ɪɴғᴏ</u></b> :\n\n<b>ᴠᴏɪᴄᴇ : {ac_audio}\nᴠɪᴅᴇᴏ  : {ac_video}</b></blockquote>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("ᴄʟᴏsᴇ 🍂", callback_data=f"close")]]
        ),
    )
