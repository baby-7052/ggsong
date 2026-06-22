import asyncio
import os

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InputMediaPhoto, Message

import config
from Opus import app
from Opus.misc import db
from Opus.utils import SignalBin, get_channeplayCB, seconds_to_min
from Opus.utils.database import get_cmode, is_active_chat, is_music_playing
from Opus.utils.decorators.language import language, languageCB
from Opus.utils.inline import queue_back_markup, queue_markup
from config import BANNED_USERS

basic = {}


def get_image(videoid):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"
    else:
        return config.YOUTUBE_IMG_URL


def get_duration(playing):
    file_path = playing[0]["file"]
    if "index_" in file_path or "live_" in file_path:
        return "Unknown"
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return "Unknown"
    else:
        return "Inline"


@app.on_message(
    filters.command(["queue", "cqueue", "player", "cplayer", "playing", "cplaying"])
    & filters.group
    & ~BANNED_USERS
)
@language
async def get_queue(client, message: Message, _):
    if message.command[0][0] == "c":
        chat_id = await get_cmode(message.chat.id)
        if chat_id is None:
            return await message.reply_text(_["setting_7"])
        try:
            await app.get_chat(chat_id)
        except:
            return await message.reply_text(_["cplay_4"])
        cplay = True
    else:
        chat_id = message.chat.id
        cplay = False
    if not await is_active_chat(chat_id):
        return await message.reply_text(_["general_5"])
    got = db.get(chat_id)
    if not got:
        return await message.reply_text(_["queue_2"])
    file = got[0]["file"]
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = (got[0]["title"]).title()
    typo = (got[0]["streamtype"]).title()
    DUR = get_duration(got)
    if "live_" in file:
        IMAGE = get_image(videoid)
    elif "vid_" in file:
        IMAGE = get_image(videoid)
    elif "index_" in file:
        IMAGE = config.STREAM_IMG_URL
    else:
        if videoid == "telegram":
            IMAGE = (
                config.TELEGRAM_AUDIO_URL
                if typo == "Audio"
                else config.TELEGRAM_VIDEO_URL
            )
        elif videoid == "soundcloud":
            IMAGE = config.SOUNCLOUD_IMG_URL
        else:
            IMAGE = get_image(videoid)
    send = _["queue_6"] if DUR == "Unknown" else _["queue_7"]
    cap = _["queue_8"].format(app.mention, title, typo, user, send)
    upl = (
        queue_markup(_, DUR, "c" if cplay else "g", videoid)
        if DUR == "Unknown"
        else queue_markup(
            _,
            DUR,
            "c" if cplay else "g",
            videoid,
            seconds_to_min(got[0]["played"]),
            got[0]["dur"],
        )
    )
    basic[videoid] = True
    mystic = await message.reply_photo(IMAGE, caption=cap, reply_markup=upl)
    if DUR != "Unknown":
        try:
            while db[chat_id][0]["vidid"] == videoid:
                await asyncio.sleep(5)
                if await is_active_chat(chat_id):
                    if basic[videoid]:
                        if await is_music_playing(chat_id):
                            try:
                                buttons = queue_markup(
                                    _,
                                    DUR,
                                    "c" if cplay else "g",
                                    videoid,
                                    seconds_to_min(db[chat_id][0]["played"]),
                                    db[chat_id][0]["dur"],
                                )
                                await mystic.edit_reply_markup(reply_markup=buttons)
                            except FloodWait:
                                pass
                        else:
                            pass
                    else:
                        break
                else:
                    break
        except:
            return


@app.on_callback_query(filters.regex("GetTimer") & ~BANNED_USERS)
async def quite_timer(client, CallbackQuery: CallbackQuery):
    try:
        await CallbackQuery.answer()
    except:
        pass


@app.on_callback_query(filters.regex("GetQueued") & ~BANNED_USERS)
@languageCB
async def queued_tracks(client, CallbackQuery: CallbackQuery, _):
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    what, videoid = callback_request.split("|")
    try:
        chat_id, channel = await get_channeplayCB(_, what, CallbackQuery)
    except:
        return
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    if len(got) == 1:
        return await CallbackQuery.answer(_["queue_5"], show_alert=True)
    await CallbackQuery.answer()
    basic[videoid] = False
    
    j = 0
    msg = "<blockquote><b>🎧 ᴀᴜʀᴇx ᴄᴏʟʟᴀʙᴏʀᴀᴛɪᴠᴇ ǫᴜᴇᴜᴇ</b></blockquote>\n\n"
    for x in got[:11]:
        j += 1
        votes_count = x.get("votes", 0)
        votes_text = f" (🔺 {votes_count} votes)" if j > 1 else ""
        if j == 1:
            msg += f'<b>🔊 Sᴛʀᴇᴀᴍɪɴɢ :</b>\n<blockquote>✨ <b>{x["title"]}</b>\n👤 <b>ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ :</b> {x["by"]}</blockquote>\n\n'
        elif j == 2:
            msg += f'<b>📋 Uᴘᴄᴏᴍɪɴɢ Qᴜᴇᴜᴇ :</b>\n<blockquote><b>1. {x["title"]}</b>{votes_text}\n👤 {x["by"]} | 🕒 {x["dur"]}</blockquote>\n'
        else:
            msg += f'<blockquote><b>{j-1}. {x["title"]}</b>{votes_text}\n👤 {x["by"]} | 🕒 {x["dur"]}</blockquote>\n'
            
    if len(got) > 11:
        msg += f"\n<blockquote><i>... ᴀɴᴅ {len(got)-11} ᴍᴏʀᴇ sᴏɴɢs ɪɴ ǫᴜᴇᴜᴇ.</i></blockquote>"
        
    buttons = []
    j = 0
    for x in got[1:6]:
        j += 1
        v_id = x["vidid"]
        buttons.append([
            InlineKeyboardButton(
                text=f"🔺 uᴘᴠᴏᴛᴇ {j}",
                callback_data=f"VoteUp {chat_id}|{v_id}|{what}"
            ),
            InlineKeyboardButton(
                text=f"🔻 dᴏᴡɴᴠᴏᴛᴇ {j}",
                callback_data=f"VoteDown {chat_id}|{v_id}|{what}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text=_["BACK_BUTTON"],
            callback_data=f"queue_back_timer {what}",
        ),
        InlineKeyboardButton(
            text=_["CLOSE_BUTTON"],
            callback_data="close",
        )
    ])
    
    med = InputMediaPhoto(
        media="https://telegra.ph//file/6f7d35131f69951c74ee5.jpg",
        caption="<blockquote><b>📊 ʟᴏᴀᴅɪɴɢ ᴄᴏʟʟᴀʙᴏʀᴀᴛɪᴠᴇ ǫᴜᴇᴜᴇ...</b></blockquote>",
    )
    try:
        await CallbackQuery.edit_message_media(media=med)
    except:
        pass
        
    await asyncio.sleep(0.5)
    await CallbackQuery.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons))


@app.on_callback_query(filters.regex(r"^(VoteUp|VoteDown)") & ~BANNED_USERS)
@languageCB
async def vote_callback(client, CallbackQuery: CallbackQuery, _):
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    callback_data = CallbackQuery.data.split()
    action = callback_data[0]
    payload = callback_data[1]
    
    chat_id_str, vidid, what = payload.split("|")
    chat_id = int(chat_id_str)
    user_id = CallbackQuery.from_user.id
    
    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer("Nᴏ ᴀᴄᴛɪᴠᴇ ǫᴜᴇᴜᴇ ғᴏᴜɴᴅ. ❌", show_alert=True)
        
    track = None
    for x in got[1:]:
        if x.get("vidid") == vidid:
            track = x
            break
            
    if not track:
        return await CallbackQuery.answer("Sᴏɴɢ ɴᴏ ʟᴏɴɢᴇʀ ɪɴ ǫᴜᴇᴜᴇ. ❌", show_alert=True)
        
    if "votes" not in track:
        track["votes"] = 0
    if "voters" not in track:
        track["voters"] = {}
        
    current_vote = track["voters"].get(user_id, 0)
    target_vote = 1 if action == "VoteUp" else -1
    
    if current_vote == target_vote:
        return await CallbackQuery.answer("ʏᴏᴜ ʜᴀᴠᴇ ᴀʟʀᴇᴀᴅʏ ᴠᴏᴛᴇᴅ ᴛʜɪs ᴡᴀʏ! ⚠️", show_alert=True)
        
    track["voters"][user_id] = target_vote
    track["votes"] = sum(track["voters"].values())
    
    upcoming = got[1:]
    upcoming.sort(key=lambda x: x.get("votes", 0), reverse=True)
    db[chat_id] = [got[0]] + upcoming
    
    await CallbackQuery.answer("ᴠᴏᴛᴇ ʀᴇᴄᴏʀᴅᴇᴅ! 🔺" if target_vote == 1 else "ᴠᴏᴛᴇ ʀᴇᴄᴏʀᴅᴇᴅ! 🔻")
    
    got = db[chat_id]
    j = 0
    msg = "<blockquote><b>🎧 ᴀᴜʀᴇx ᴄᴏʟʟᴀʙᴏʀᴀᴛɪᴠᴇ ǫᴜᴇᴜᴇ</b></blockquote>\n\n"
    for x in got[:11]:
        j += 1
        votes_count = x.get("votes", 0)
        votes_text = f" (🔺 {votes_count} votes)" if j > 1 else ""
        if j == 1:
            msg += f'<b>🔊 Sᴛʀᴇᴀᴍɪɴɢ :</b>\n<blockquote>✨ <b>{x["title"]}</b>\n👤 <b>ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ :</b> {x["by"]}</blockquote>\n\n'
        elif j == 2:
            msg += f'<b>📋 Uᴘᴄᴏᴍɪɴɢ Qᴜᴇᴜᴇ :</b>\n<blockquote><b>1. {x["title"]}</b>{votes_text}\n👤 {x["by"]} | 🕒 {x["dur"]}</blockquote>\n'
        else:
            msg += f'<blockquote><b>{j-1}. {x["title"]}</b>{votes_text}\n👤 {x["by"]} | 🕒 {x["dur"]}</blockquote>\n'
            
    if len(got) > 11:
        msg += f"\n<blockquote><i>... ᴀɴᴅ {len(got)-11} ᴍᴏʀᴇ sᴏɴɢs ɪɴ ǫᴜᴇᴜᴇ.</i></blockquote>"
        
    buttons = []
    j = 0
    for x in got[1:6]:
        j += 1
        v_id = x["vidid"]
        buttons.append([
            InlineKeyboardButton(
                text=f"🔺 uᴘᴠᴏᴛᴇ {j}",
                callback_data=f"VoteUp {chat_id}|{v_id}|{what}"
            ),
            InlineKeyboardButton(
                text=f"🔻 dᴏᴡɴᴠᴏᴛᴇ {j}",
                callback_data=f"VoteDown {chat_id}|{v_id}|{what}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text=_["BACK_BUTTON"],
            callback_data=f"queue_back_timer {what}",
        ),
        InlineKeyboardButton(
            text=_["CLOSE_BUTTON"],
            callback_data="close",
        )
    ])
    
    try:
        await CallbackQuery.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        pass


@app.on_callback_query(filters.regex("queue_back_timer") & ~BANNED_USERS)
@languageCB
async def queue_back(client, CallbackQuery: CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    cplay = callback_data.split(None, 1)[1]
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    await CallbackQuery.answer(_["set_cb_5"], show_alert=True)
    file = got[0]["file"]
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = (got[0]["title"]).title()
    typo = (got[0]["streamtype"]).title()
    DUR = get_duration(got)
    if "live_" in file:
        IMAGE = get_image(videoid)
    elif "vid_" in file:
        IMAGE = get_image(videoid)
    elif "index_" in file:
        IMAGE = config.STREAM_IMG_URL
    else:
        if videoid == "telegram":
            IMAGE = (
                config.TELEGRAM_AUDIO_URL
                if typo == "Audio"
                else config.TELEGRAM_VIDEO_URL
            )
        elif videoid == "soundcloud":
            IMAGE = config.SOUNCLOUD_IMG_URL
        else:
            IMAGE = get_image(videoid)
    send = _["queue_6"] if DUR == "Unknown" else _["queue_7"]
    cap = _["queue_8"].format(app.mention, title, typo, user, send)
    upl = (
        queue_markup(_, DUR, cplay, videoid)
        if DUR == "Unknown"
        else queue_markup(
            _,
            DUR,
            cplay,
            videoid,
            seconds_to_min(got[0]["played"]),
            got[0]["dur"],
        )
    )
    basic[videoid] = True

    med = InputMediaPhoto(media=IMAGE, caption=cap)
    mystic = await CallbackQuery.edit_message_media(media=med, reply_markup=upl)
    if DUR != "Unknown":
        try:
            while db[chat_id][0]["vidid"] == videoid:
                await asyncio.sleep(5)
                if await is_active_chat(chat_id):
                    if basic[videoid]:
                        if await is_music_playing(chat_id):
                            try:
                                buttons = queue_markup(
                                    _,
                                    DUR,
                                    cplay,
                                    videoid,
                                    seconds_to_min(db[chat_id][0]["played"]),
                                    db[chat_id][0]["dur"],
                                )
                                await mystic.edit_reply_markup(reply_markup=buttons)
                            except FloodWait:
                                pass
                        else:
                            pass
                    else:
                        break
                else:
                    break
        except:
            return
