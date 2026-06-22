import asyncio

from pyrogram import filters, errors
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Opus import Vortex, YouTube, app
from Opus.core.call import Signal
from Opus.misc import SUDOERS, db
from Opus.utils.database import (
    get_active_chats,
    get_lang,
    get_upvote_count,
    is_active_chat,
    is_music_playing,
    is_nonadmin_chat,
    music_off,
    music_on,
    set_loop,
    get_thumb_setting,
    add_banned_user,
    is_banned_user,
    is_sync_lyrics,
)
from Opus.platforms import Lyrics
from Opus.utils.downloader import download_url
from Opus.utils.decorators.language import languageCB
from Opus.utils.formatters import seconds_to_min
from Opus.utils.inline import close_markup, stream_markup, stream_markup_timer
from Opus.utils.stream.autoclear import auto_clean
from Opus.utils.stream.stream import stream
from Opus.utils.thumbnails import get_thumb

from config import (
    BANNED_USERS,
    SUPPORT_CHAT,
    SOUNCLOUD_IMG_URL,
    STREAM_IMG_URL,
    TELEGRAM_AUDIO_URL,
    TELEGRAM_VIDEO_URL,
    adminlist,
    confirmer,
    votemode,
    autoclean,
)
from strings import get_string

checker = {}
upvoters = {}
# Track last processed vidid per chat to detect skips/# 0. Global state for markup optimization
last_processed_vidid = {}
last_markup_state = {} # Stores (chat_id, vidid, played_min, lyric_line)

async def delete_after_delay(message, delay=86400):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

def parse_duration_to_seconds(dur):
    try:
        if isinstance(dur, int):
            return dur
        parts = str(dur).split(":")
        parts = [int(p) for p in parts if p != ""]
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except:
        return 0
    return 0

@app.on_callback_query(filters.regex("ADMIN") & ~BANNED_USERS)
@languageCB
async def del_back_playlist(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    if "|" not in callback_request:
        return await CallbackQuery.answer("Invalid callback data.", show_alert=True)
    command, chat = callback_request.split("|")
    if "_" in str(chat):
        bet = chat.split("_")
        chat = bet[0]
        counter = bet[1]
    chat_id = int(chat)
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    mention = CallbackQuery.from_user.mention
    thumb_mode = await get_thumb_setting(chat_id)

    if command == "UpVote":
        if chat_id not in votemode:
            votemode[chat_id] = {}
        if chat_id not in upvoters:
            upvoters[chat_id] = {}

        voters = (upvoters[chat_id]).get(CallbackQuery.message.id)
        if not voters:
            upvoters[chat_id][CallbackQuery.message.id] = []

        vote = (votemode[chat_id]).get(CallbackQuery.message.id)
        if not vote:
            votemode[chat_id][CallbackQuery.message.id] = 0

        if CallbackQuery.from_user.id in upvoters[chat_id][CallbackQuery.message.id]:
            (upvoters[chat_id][CallbackQuery.message.id]).remove(
                CallbackQuery.from_user.id
            )
            votemode[chat_id][CallbackQuery.message.id] -= 1
        else:
            (upvoters[chat_id][CallbackQuery.message.id]).append(
                CallbackQuery.from_user.id
            )
            votemode[chat_id][CallbackQuery.message.id] += 1
        upvote = await get_upvote_count(chat_id)
        get_upvotes = int(votemode[chat_id][CallbackQuery.message.id])
        if get_upvotes >= upvote:
            votemode[chat_id][CallbackQuery.message.id] = upvote
            try:
                exists = confirmer[chat_id][CallbackQuery.message.id]
                current = db[chat_id][0]
            except:
                return await CallbackQuery.edit_message_text(f"ғᴀɪʟᴇᴅ.")
            try:
                if current["vidid"] != exists["vidid"]:
                    return await CallbackQuery.edit_message_text(_["admin_35"])
                if current["file"] != exists["file"]:
                    return await CallbackQuery.edit_message_text(_["admin_35"])
            except:
                return await CallbackQuery.edit_message_text(_["admin_36"])
            try:
                await CallbackQuery.edit_message_text(_["admin_37"].format(upvote))
            except:
                pass
            command = counter
            mention = "ᴜᴘᴠᴏᴛᴇs"
        else:
            if (
                CallbackQuery.from_user.id
                in upvoters[chat_id][CallbackQuery.message.id]
            ):
                await CallbackQuery.answer(_["admin_38"], show_alert=True)
            else:
                await CallbackQuery.answer(_["admin_39"], show_alert=True)
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text=f"UpVote {get_upvotes}",
                            callback_data=f"ADMIN  UpVote|{chat_id}_{counter}",
                        )
                    ]
                ]
            )
            await CallbackQuery.answer(_["admin_40"], show_alert=True)
            return await CallbackQuery.edit_message_reply_markup(reply_markup=upl)
    else:
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            if CallbackQuery.from_user.id not in SUDOERS:
                admins = adminlist.get(CallbackQuery.message.chat.id)
                if not admins:
                    return await CallbackQuery.answer(_["admin_13"], show_alert=True)
                else:
                    if CallbackQuery.from_user.id not in admins:
                        return await CallbackQuery.answer(
                            _["admin_14"], show_alert=True
                        )
    if command == "Pause":
        if not await is_music_playing(chat_id):
            return await CallbackQuery.answer(_["admin_1"], show_alert=True)
        await CallbackQuery.answer()
        await music_off(chat_id)
        await Signal.pause_stream(chat_id)
        sent_msg = await CallbackQuery.message.reply_text(_["admin_2"].format(mention))
        asyncio.create_task(delete_after_delay(sent_msg, 86400))
    elif command == "Resume":
        if await is_music_playing(chat_id):
            return await CallbackQuery.answer(_["admin_3"], show_alert=True)
        await CallbackQuery.answer()
        await music_on(chat_id)
        await Signal.resume_stream(chat_id)
        sent_msg = await CallbackQuery.message.reply_text(_["admin_4"].format(mention))
        asyncio.create_task(delete_after_delay(sent_msg, 86400))
    elif command == "Stop" or command == "End":
        await CallbackQuery.answer()
        try:
            await Signal.stop_stream(chat_id)
        except:
            pass
        try:
            await music_off(chat_id)
        except:
            pass
        try:
            await set_loop(chat_id, 0)
        except:
            pass
        try:
            if db.get(chat_id) and db[chat_id] and db[chat_id][0].get("mystic"):
                await db[chat_id][0]["mystic"].delete()
        except:
            pass
        try:
            db.pop(chat_id, None)
        except:
            pass
        await CallbackQuery.message.delete()
    elif command == "Skip" or command == "Replay":
        check = db.get(chat_id)
        if not check:
            return await CallbackQuery.answer(_["admin_27"], show_alert=True)

        if command == "Skip":
            txt = f"<blockquote><b>ᴛʀᴀᴄᴋ sᴋɪᴩᴩᴇᴅ</b>\n<b>ʙʏ :</b> {mention} 🛸</blockquote>"
            popped = None
            try:
                popped = check.pop(0)
                if popped:
                    await auto_clean(popped)
                if not check:
                    try:
                        await CallbackQuery.edit_message_text(txt)
                    except:
                        pass
                    sent_msg = await CallbackQuery.message.reply_text(
                        text=_["admin_6"].format(
                            mention, CallbackQuery.message.chat.title
                        ),
                        reply_markup=close_markup(_),
                    )
                    asyncio.create_task(delete_after_delay(sent_msg, 86400))
                    try:
                        if db.get(chat_id) and db[chat_id] and db[chat_id][0].get("mystic"):
                            await db[chat_id][0]["mystic"].delete()
                    except:
                        pass
                    try:
                        await Signal.stop_stream(chat_id)
                    except:
                        pass
                    try:
                        await music_off(chat_id)
                    except:
                        pass
                    try:
                        await set_loop(chat_id, 0)
                    except:
                        pass
                    try:
                        db.pop(chat_id, None)
                    except:
                        pass
                    return
            except:
                pass
        else:
            txt = f"<b><blockquote>≥ ᴛʀᴀᴄᴋ ʀᴇ-ᴘʟᴀʏᴇᴅ\n• ʙʏ : {mention} 🔖</blockquote></b>"

        try:
            if db.get(chat_id) and db[chat_id] and db[chat_id][0].get("mystic"):
                await db[chat_id][0]["mystic"].delete()
        except:
            pass

        await CallbackQuery.answer()
        if not check:
             return
        queued = check[0]["file"]
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        duration = check[0]["dur"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        thumbnail = check[0].get("thumb")
        status = True if str(streamtype) == "video" else None
        db[chat_id][0]["played"] = 0
        exis = check[0].get("old_dur")
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


        user_id = check[0].get("user_id", 0)
        from Opus.utils.database import is_on_playlist
        liked = await is_on_playlist(user_id, videoid)
        
        button = stream_markup(_, videoid, chat_id, liked=liked)

        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await CallbackQuery.message.reply_text(
                    text=_["admin_7"].format(title),
                    reply_markup=close_markup(_),
                )
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
            try:
                await Signal.skip_stream(chat_id, link, video=status, image=image)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            caption_text = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                duration,
                user,
            )
            if thumb_mode:
                img = await get_thumb(videoid, force_url=thumbnail, force_title=title, chat_id=chat_id)
                run = await CallbackQuery.message.reply_photo(
                    photo=img,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                    disable_web_page_preview=True,
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            try:
                await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            except:
                pass
            sec = check[0].get("seconds") or parse_duration_to_seconds(duration)
            if sec and sec > 0:
                asyncio.create_task(delete_after_delay(run, sec + 2))

        elif "vid_" in queued:
            mystic_dl = await CallbackQuery.message.reply_text(
                _["call_7"], disable_web_page_preview=True
            )
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
                        mystic_dl,
                        videoid=True,
                        video=status,
                    )
            except Exception as e:
                # LOGGER(__name__).error(f"Skip Download Error: {e}")
                return await mystic_dl.edit_text(_["call_6"])
            try:
                image = await YouTube.thumbnail(videoid, True)
            except:
                image = None
            try:
                await Signal.skip_stream(chat_id, file_path, video=status, image=image)
            except:
                return await mystic_dl.edit_text(_["call_6"])
            caption_text = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                duration,
                user,
            )
            if thumb_mode:
                img = await get_thumb(videoid, force_url=thumbnail, force_title=title, chat_id=chat_id)
                run = await CallbackQuery.message.reply_photo(
                    photo=img,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                    disable_web_page_preview=True,
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
            try:
                await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            except:
                pass
            await mystic_dl.delete()
            sec = check[0].get("seconds") or parse_duration_to_seconds(duration)
            if sec and sec > 0:
                asyncio.create_task(delete_after_delay(run, sec + 2))

        elif "index_" in queued:
            try:
                await Signal.skip_stream(chat_id, videoid, video=status)
            except:
                return await CallbackQuery.message.reply_text(_["call_6"])
            caption_text = _["stream_2"].format(user)
            if thumb_mode:
                run = await CallbackQuery.message.reply_photo(
                    photo=STREAM_IMG_URL,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await CallbackQuery.message.reply_text(
                    caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                    disable_web_page_preview=True,
                )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            try:
                await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            except:
                pass
            sec = check[0].get("seconds") or parse_duration_to_seconds(duration)
            if sec and sec > 0:
                asyncio.create_task(delete_after_delay(run, sec + 2))

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
                return await CallbackQuery.message.reply_text(_["call_6"])
            if videoid in ["telegram", "soundcloud"]:
                caption_text = _["stream_1"].format(
                    SUPPORT_CHAT, title[:23], duration, user
                )
                photo_url = TELEGRAM_AUDIO_URL if streamtype == "audio" else TELEGRAM_VIDEO_URL
                if videoid == "soundcloud":
                    photo_url = SOUNCLOUD_IMG_URL if streamtype == "audio" else TELEGRAM_VIDEO_URL
                if thumb_mode:
                    run = await CallbackQuery.message.reply_photo(
                        photo=photo_url,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                        disable_web_page_preview=True,
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                caption_text = _["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    duration,
                    user,
                )
                if thumb_mode:
                    img = await get_thumb(videoid, force_url=thumbnail, force_title=title, chat_id=chat_id)
                    run = await CallbackQuery.message.reply_photo(
                        photo=img,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await CallbackQuery.message.reply_text(
                        caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                        disable_web_page_preview=True,
                    )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            try:
                await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))
            except:
                pass
            sec = check[0].get("seconds") or parse_duration_to_seconds(duration)
            if sec and sec > 0:
                asyncio.create_task(delete_after_delay(run, sec + 2))

@app.on_callback_query(filters.regex("^V\|") & ~BANNED_USERS)
async def vortex_playlist_cb(client, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    try:
        parts = callback_data.split("|")
        if len(parts) < 6:
            return await CallbackQuery.answer("🚫 ᴇʀʀᴏʀ: ʙᴜᴛᴛᴏɴ ᴅᴀᴛᴀ ɪs ᴛʀᴜɴᴄᴀᴛᴇᴅ.", show_alert=True)
        
        p_id = parts[1]
        user_id = parts[2]
        chat_id = parts[3]
        video = parts[4]
        fplay = parts[5]
    except (ValueError, IndexError):
        return await CallbackQuery.answer("🚫 ᴇʀʀᴏʀ: ʙᴜᴛᴛᴏɴ ᴅᴀᴛᴀ ɪs ᴍᴀʟғᴏʀᴍᴇᴅ.", show_alert=True)
    
    if CallbackQuery.from_user.id != int(user_id):
        return await CallbackQuery.answer("ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴛʜᴇ ᴏɴᴇ ᴡʜᴏ sᴇᴀʀᴄʜᴇᴅ ᴛʜɪs ᴘʟᴀʏʟɪsᴛ.", show_alert=True)

    await CallbackQuery.answer("ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ... ғᴇᴛᴄʜɪɴɢ ᴘʟᴀʏʟɪsᴛ ᴛʀᴀᴄᴋs.", show_alert=True)
    mystic = CallbackQuery.message
    await mystic.edit_text("<b><blockquote>🌀 ғᴇᴛᴄʜɪɴɢ ᴘʟᴀʏʟɪsᴛ... ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ.</blockquote></b>")
    
    try:
        playlist_tracks = await Vortex.get_playlist_details(p_id)
    except Exception as e:
        return await mystic.edit_text(f"<b><blockquote>🚫 ᴀᴘɪ ᴇʀʀᴏʀ:\n\n{e}</blockquote></b>")

    if not playlist_tracks:
        return await mystic.edit_text("<b><blockquote>🚫 ᴇʀʀᴏʀ: ᴜɴᴀʙʟᴇ ᴛᴏ ғᴇᴛᴄʜ ᴛʀᴀᴄᴋs ғᴏʀ ᴛʜɪs ᴘʟᴀʏʟɪsᴛ.</blockquote></b>")

    language = await get_lang(int(chat_id))
    _ = get_string(language)
    
    await stream(
        _,
        mystic,
        user_id,
        playlist_tracks,
        int(chat_id),
        CallbackQuery.from_user.first_name,
        int(chat_id),
        video=video == "1",
        streamtype="playlist",
        forceplay=fplay == "1",
    )

async def markup_timer():
    while not await asyncio.sleep(6):
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing or not playing[0]:
                    continue
                
                duration_seconds = int(playing[0]["seconds"])
                if duration_seconds == 0:
                    continue
                
                current_vidid = playing[0].get("vidid")
                current_title = playing[0].get("title")
                mystic = playing[0].get("mystic")
                
                if not mystic:
                    continue

                # 1. Initialize checker for this chat/message if missing
                if chat_id not in checker:
                    checker[chat_id] = {}
                if mystic.id not in checker[chat_id]:
                    checker[chat_id][mystic.id] = True # Default to True

                # 2. Detect Track Change/Skip
                if last_processed_vidid.get(chat_id) != current_vidid:
                    # New track detected! Clear any stale lyrics data
                    playing[0].pop("synced_lyrics", None)
                    playing[0].pop("plain_lyrics", None)
                    playing[0].pop("lyric_fetching", None)
                    last_processed_vidid[chat_id] = current_vidid

                try:
                    check = checker[chat_id][mystic.id]
                    if check is False:
                        continue
                except:
                    continue

                try:
                    language = await get_lang(chat_id)
                    _ = get_string(language)
                except:
                    _ = get_string("en")

                try:
                    lyric_line = None
                    if await is_sync_lyrics(chat_id):
                        if "synced_lyrics" not in playing[0]:
                            # Start background fetch if not already in progress
                            if not playing[0].get("lyric_fetching"):
                                playing[0]["lyric_fetching"] = True
                                
                                async def fetch_lyrics(t_dict, q_title, q_vidid):
                                    res = await Lyrics.get_synced_lyrics(q_title)
                                    # Strict validation: Check both title AND vidid match current state
                                    if t_dict.get("title") == q_title and t_dict.get("vidid") == q_vidid:
                                        t_dict["synced_lyrics"] = res if res else False
                                        # Also fetch plain if synced failed/was string
                                        if not res or isinstance(res, str):
                                            res_p = await Lyrics.get_lyrics(q_title)
                                            if t_dict.get("title") == q_title and t_dict.get("vidid") == q_vidid:
                                                t_dict["plain_lyrics"] = res_p if res_p else False
                                    t_dict["lyric_fetching"] = False
                                
                                asyncio.create_task(fetch_lyrics(playing[0], current_title, current_vidid))
                        
                        synced = playing[0].get("synced_lyrics")
                        if synced and isinstance(synced, list):
                            # Exact synced lyrics (from Apexi/LRCLIB)
                            current_sec = playing[0]["played"]
                            for l_sec, text in reversed(synced):
                                if current_sec >= l_sec:
                                    lyric_line = text
                                    break
                        else:
                            # Use plain_lyrics if synced is string or not available
                            plain = synced if isinstance(synced, str) else playing[0].get("plain_lyrics")
                            
                            if plain and isinstance(plain, str):
                                lines = [l.strip() for l in plain.split("\n") if l.strip() and len(l.strip()) > 3]
                                if lines:
                                    # Cycle through one line every 12 seconds for better stability
                                    idx = (playing[0]["played"] // 12) % len(lines)
                                    lyric_line = lines[idx]

                        if lyric_line and len(lyric_line) > 25:
                            import textwrap
                            parts = textwrap.wrap(lyric_line, width=25)
                            if parts:
                                p_idx = (playing[0]["played"] // 3) % len(parts)
                                lyric_line = parts[p_idx]
                    
                    # Calculate show_lyrics visibility
                    show_lyrics = False
                    if await is_sync_lyrics(chat_id):
                        syn = playing[0].get("synced_lyrics")
                        pla = playing[0].get("plain_lyrics")
                        if syn or pla:
                            show_lyrics = True

                    # Seeker bar progress in minutes (changes every 60s)
                    played_min = playing[0]["played"] // 60
                    
                    user_id = playing[0].get("user_id", 0)
                    from Opus.utils.database import is_on_playlist
                    liked = await is_on_playlist(user_id, current_vidid)

                    # 4. State-based optimization: Skip update if nothing changed
                    # If lyrics are showing, we only care if the lyric line is different
                    # If lyrics are NOT showing, we care about the seeker bar (played time)
                    state = (chat_id, current_vidid, lyric_line, played_min if not lyric_line else None, liked)
                    if last_markup_state.get(chat_id) == state:
                        continue

                    buttons = stream_markup_timer(
                        _,
                        current_vidid,
                        chat_id,
                        seconds_to_min(playing[0]["played"]),
                        playing[0]["dur"],
                        liked=liked,
                        lyric_line=lyric_line,
                        show_lyrics=show_lyrics,
                    )
                    
                    try:
                        await mystic.edit_reply_markup(
                            reply_markup=InlineKeyboardMarkup(buttons)
                        )
                        last_markup_state[chat_id] = state
                    except errors.FloodWait as e:
                        await asyncio.sleep(e.value)
                        continue
                    except Exception:
                        continue
                except Exception as e:
                    # LOGGER(__name__).error(f"UI Update Error: {e}")
                    continue
            except:
                continue

asyncio.create_task(markup_timer())

@app.on_callback_query(filters.regex("GBAN_SEC_USER") & SUDOERS)
async def gban_sec_user_cb(client, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    user_id = int(callback_data.split("|")[1])
    
    if await is_banned_user(user_id):
        return await CallbackQuery.answer("User is already globally banned.", show_alert=True)
    
    if user_id in SUDOERS:
        return await CallbackQuery.answer("You cannot ban a sudo user!", show_alert=True)
    
    await add_banned_user(user_id)
    if user_id not in BANNED_USERS:
        BANNED_USERS.add(user_id)
    
    await CallbackQuery.answer("User has been globally banned successfully.", show_alert=True)
    
    # Update the report message to show it's handled
    try:
        await CallbackQuery.edit_message_text(
            f"{CallbackQuery.message.text}\n\n✅ **Handled:** User has been GBANNED by {CallbackQuery.from_user.mention}.",
            reply_markup=None
        )
    except:
        pass
