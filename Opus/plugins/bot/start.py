import time
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from youtubesearchpython.future import VideosSearch
import config
from Opus import app
from Opus.misc import _boot_, SUDOERS
from Opus.plugins.sudo.sudoers import sudoers_list
from Opus.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from Opus.utils.decorators.language import LanguageStart
from Opus.utils.formatters import get_readable_time
from Opus.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS
from strings import get_string


@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    await add_served_user(message.from_user.id)
    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]
        if name[0:4] == "help":
            keyboard = help_pannel(_)
            return await message.reply_photo(
                photo=config.START_IMG_URL,
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
            )
        if name[0:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"<blockquote><b>» <a href='https://t.me/{message.from_user.username}'>ᴜsᴇʀ</a> ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ sᴜᴅᴏʟɪsᴛ</b>\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code></blockquote>",
                    disable_web_page_preview=True
                )
            return
        if name[0:3] == "inf":
            m = await message.reply_text("🔎")
            query = (str(name)).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"
            results = VideosSearch(query, limit=1)
            results_dict = await results.next()
            title = "Unknown"
            duration = "Unknown"
            views = "Unknown"
            published = "Unknown"
            channellink = config.SUPPORT_CHAT
            channel = "Unknown"
            link = "https://www.youtube.com"
            if results_dict and "result" in results_dict:
                for result in results_dict["result"]:
                    title = result.get("title", "Unknown")
                    duration = result.get("duration", "Unknown")
                    views = result.get("viewCount", {}).get("short", "Unknown")
                    channellink = result.get("channel", {}).get("link", config.SUPPORT_CHAT)
                    channel = result.get("channel", {}).get("name", "Unknown")
                    link = result.get("link", "https://www.youtube.com")
                    published = result.get("publishedTime", "Unknown")
            searched_text = _["start_6"].format(
                title, duration, views, published, channellink, channel, app.mention
            )
            key = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(text=_["S_B_8"], url=link),
                        InlineKeyboardButton(text=_["S_B_9"], url=config.SUPPORT_CHAT),
                    ],
                ]
            )
            await m.delete()
            await message.reply(
                text=searched_text,
                reply_markup=key,
            )
            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"<blockquote><b>» <a href='https://t.me/{message.from_user.username}'>ᴜsᴇʀ</a> ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ ᴛʀᴀᴄᴋ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code></blockquote>",
                    disable_web_page_preview=False
                )
    else:
        out = private_panel(_)         
        await message.reply(
            text=f'<blockquote><b>ʜᴇʏ {message.from_user.mention}, ɪ’ᴍ sᴛᴏʀᴍɪғʏ 🧸</b></blockquote>\n'
                 f'<blockquote><b>ʏᴏᴜʀ ɴᴇxᴛ-ɢᴇɴ ᴍᴜsɪᴄ ᴄᴏᴍᴘᴀɴɪᴏɴ. ᴄᴏᴍᴘʟᴇᴛᴇʟʏ ʀᴇᴡʀɪᴛᴛᴇɴ ғᴏʀ ᴜɴᴍᴀᴛᴄʜᴇᴅ sᴘᴇᴇᴅ, ᴜʟᴛʀᴀ-sᴛᴇᴀʟᴛʜ ᴘᴇʀғᴏʀᴍᴀɴᴄᴇ, ᴀɴᴅ ᴀɴ ᴇʟɪᴛᴇ ʟɪsᴛᴇɴɪɴɢ ᴇxᴘᴇʀɪᴇɴᴄᴇ.</b></blockquote>\n'
                 f'<b><blockquote><a href="https://files.catbox.moe/njlbdy.jpg">✨</a> ɴᴇᴡ ᴄᴀᴘᴀʙɪʟɪᴛɪᴇs:\n'
                 f'• ʟɪɢʜᴛɴɪɴɢ-ғᴀsᴛ ᴄᴀᴄʜᴇʟᴇss ᴀʀᴄʜɪᴛᴇᴄᴛᴜʀᴇ\n'
                 f'• ᴘᴜʀᴇ ᴘʀᴇᴍɪᴜᴍ ᴀᴜᴅɪᴏ ᴡɪᴛʜ ᴢᴇʀᴏ ʟᴀɢ\n'
                 f'• sᴛᴀᴛᴇ-ᴏғ-ᴛʜᴇ-ᴀʀᴛ ᴠɪsᴜᴀʟs & ᴄᴀʀᴅs</blockquote></b>\n'
                 f'<blockquote><b>📊 ᴠᴇʀsɪᴏɴ : 𝟸𝟼.𝟻 ʀᴇ\n📚 ɴᴇᴇᴅ ɢᴜɪᴅᴀɴᴄᴇ?\nᴛᴀᴘ ʜᴇʟᴘ ᴛᴏ ᴇxᴘʟᴏʀᴇ ᴀʟʟ ᴍʏ ᴄᴀᴘᴀʙɪʟɪᴛɪᴇs.</b></blockquote>',
            reply_markup=InlineKeyboardMarkup(out),
        )
        if await is_on_off(2):
            if message.from_user.id in SUDOERS:
                return
            return await app.send_message(
                chat_id=config.LOGGER_ID,
                text=f"» <a href='https://t.me/{message.from_user.username}'>user</a> just started the bot.\nuser id : <code>{message.from_user.id}</code>\n<a href='tg://user?id={message.from_user.id}'>profile link</a>",
                disable_web_page_preview=True
            )


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)
    await message.reply(
        text=_["start_1"].format(app.mention, get_readable_time(uptime)),
        reply_markup=InlineKeyboardMarkup(out),
    )
    return await add_served_chat(message.chat.id)


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except:
                    pass
            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)
                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=sudolist",
                            config.SUPPORT_CHAT,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)

                out = start_panel(_)
                await message.reply(
                    text=_["start_3"].format(
                        message.from_user.first_name,
                        app.mention,
                        message.chat.title,
                        app.mention,
                    ),
                    reply_markup=InlineKeyboardMarkup(out),
                )
                await add_served_chat(message.chat.id)
                await message.stop_propagation()
        except Exception as ex:
            print(ex)
