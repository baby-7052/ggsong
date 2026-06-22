import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from pyrogram.errors import FloodWait
from Opus import YouTube, app, Vortex
from Opus.core.call import Signal
from Opus.misc import db
from Opus.utils.database import get_loop
from Opus.utils.decorators import AdminRightsCheck
from Opus.utils.inline import close_markup, stream_markup
from Opus.utils.stream.autoclear import auto_clean
from Opus.utils.thumbnails import get_thumb
from Opus.utils.downloader import download_url
from config import BANNED_USERS, autoclean


@app.on_message(
    filters.command(["skip", "cskip", "next", "cnext"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    if not len(message.command) < 2:
        loop = await get_loop(chat_id)
        if loop != 0:
            return await message.reply_text(_["admin_8"])
        state = message.text.split(None, 1)[1].strip()
        if state.isnumeric():
            state = int(state)
            check = db.get(chat_id)
            if check:
                count = len(check)
                if count > 2:
                    count = int(count - 1)
                    if 1 <= state <= count:
                        for x in range(state):
                            popped = None
                            try:
                                popped = check.pop(0)
                            except:
                                return await message.reply_text(_["admin_12"])
                            if popped:
                                await auto_clean(popped)
                            if not check:
                                try:
                                    await message.reply_text(
                                        text=_["admin_6"].format(
                                            message.from_user.mention,
                                            message.chat.title,
                                        ),
                                        reply_markup=close_markup(_),
                                    )
                                    await Signal.stop_stream(chat_id)
                                except:
                                    return
                                break
                    else:
                        return await message.reply_text(_["admin_11"].format(count))
                else:
                    return await message.reply_text(_["admin_10"])
            else:
                return await message.reply_text(_["queue_2"])
        else:
            return await message.reply_text(_["admin_9"])
    else:
        check = db.get(chat_id)
        popped = None
        try:
            popped = check.pop(0)
            if popped:
                await auto_clean(popped)
            if not check:
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                try:
                    return await Signal.stop_stream(chat_id)
                except:
                    return
        except:
            try:
                await message.reply_text(
                    text=_["admin_6"].format(
                        message.from_user.mention, message.chat.title
                    ),
                    reply_markup=close_markup(_),
                )
                return await Signal.stop_stream(chat_id)
            except:
                return
    if not check:
        return
    image = None
    try:
        queued = check[0]["file"]
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        duration = check[0]["dur"]
        thumbnail = check[0].get("thumb")
        status = True if str(streamtype) == "video" else None
        if chat_id in db and len(db[chat_id]) > 0:
            db[chat_id][0]["played"] = 0
            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0
            try:
                from Opus.utils.database import persist_queue
                await persist_queue(chat_id, db[chat_id])
            except:
                pass
    except Exception as e:
        config.LOGGER.error(f"Error in skip metadata: {e}")
        return
    
    user_id = check[0].get("user_id", 0)
    from Opus.utils.database import is_on_playlist
    liked = await is_on_playlist(user_id, videoid)
    
    if "live_" in queued:
        n, link = await YouTube.video(videoid, True)
        if n == 0:
            return await message.reply_text(_["admin_7"].format(title))
        try:
            image = await YouTube.thumbnail(videoid, True)
        except:
            pass
        try:
            await Signal.skip_stream(chat_id, link, video=status, image=image)
        except:
            return await message.reply_text(_["call_6"])
        button = stream_markup(_, videoid, chat_id, liked=liked)
        img = await get_thumb(videoid, force_url=thumbnail, force_title=title, chat_id=chat_id)
        try:
            run = await message.reply_photo(
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            if chat_id in db and len(db[chat_id]) > 0:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
        except FloodWait as e:
            await asyncio.sleep(e.value)
    elif "vid_" in queued:
        mystic = await message.reply_text(_["call_7"], disable_web_page_preview=True)
        try:
            if videoid.startswith("vortex_"):
                v_id = videoid.replace("vortex_", "")
                details = await Vortex.details(v_id)
                if not details:
                    raise Exception("Failed to fetch Vortex details")
                
                download_url_path = details.get("path")
                file_path = await download_url(download_url_path)
                direct = False
                autoclean.append(file_path)
            else:
                file_path, direct = await YouTube.download(
                    videoid,
                    mystic,
                    videoid=True,
                    video=status,
                )
        except Exception as e:
            config.LOGGER.error(f"Skip Download Error: {e}")
            return await mystic.edit_text(_["call_6"])
        try:
            image = await YouTube.thumbnail(videoid, True)
        except:
            image = None
        try:
            await Signal.skip_stream(chat_id, file_path, video=status, image=image)
        except:
            return await mystic.edit_text(_["call_6"])
        button = stream_markup(_, videoid, chat_id, liked=liked)
        img = await get_thumb(videoid, force_url=thumbnail, force_title=title, chat_id=chat_id)
        try:
            run = await message.reply_photo(
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            if chat_id in db and len(db[chat_id]) > 0:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        except FloodWait as e:
            await asyncio.sleep(e.value)
        await mystic.delete()
    elif "index_" in queued:
        try:
            await Signal.skip_stream(chat_id, videoid, video=status)
        except:
            return await message.reply_text(_["call_6"])
        button = stream_markup(_, videoid, chat_id, liked=liked)
        try:
            run = await message.reply_photo(
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user),
                reply_markup=InlineKeyboardMarkup(button),
            )
            if chat_id in db and len(db[chat_id]) > 0:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
        except FloodWait as e:
            await asyncio.sleep(e.value)
    else:
        if videoid == "telegram":
            image = None
        elif videoid == "soundcloud":
            image = None
        else:
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
        try:
            await Signal.skip_stream(chat_id, queued, video=status, image=image)
        except:
            return await message.reply_text(_["call_6"])
        if videoid == "telegram":
            button = stream_markup(_, videoid, chat_id, liked=liked)
            try:
                run = await message.reply_photo(
                    photo=config.TELEGRAM_AUDIO_URL
                    if str(streamtype) == "audio"
                    else config.TELEGRAM_VIDEO_URL,
                    caption=_["stream_1"].format(
                        config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                if chat_id in db and len(db[chat_id]) > 0:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
            except FloodWait as e:
                await asyncio.sleep(e.value)
        elif videoid == "soundcloud":
            button = stream_markup(_, videoid, chat_id, liked=liked)
            try:
                run = await message.reply_photo(
                    photo=config.SOUNCLOUD_IMG_URL
                    if str(streamtype) == "audio"
                    else config.TELEGRAM_VIDEO_URL,
                    caption=_["stream_1"].format(
                        config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                if chat_id in db and len(db[chat_id]) > 0:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
            except FloodWait as e:
                await asyncio.sleep(e.value)
        else:
            button = stream_markup(_, videoid, chat_id, liked=liked)
            img = await get_thumb(videoid, force_url=thumbnail, force_title=title, chat_id=chat_id)
            try:
                run = await message.reply_photo(
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                if chat_id in db and len(db[chat_id]) > 0:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"
            except FloodWait as e:
                await asyncio.sleep(e.value)
