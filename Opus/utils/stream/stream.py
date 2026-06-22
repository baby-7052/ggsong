import os
import httpx
from random import randint
from typing import Union
from pyrogram.types import InlineKeyboardMarkup

import config
from Opus import Carbon, YouTube, app
from Opus.core.call import Signal
from Opus.misc import db
from Opus.utils.database import add_active_video_chat, get_thumb_setting, is_active_chat
from Opus.utils.exceptions import AssistantErr
from Opus.utils.inline import aq_markup, close_markup, stream_markup
from Opus.utils.pastebin import SignalBin
from Opus.utils.stream.queue import put_queue, put_queue_index
from Opus.utils.thumbnails import gen_qthumb, get_thumb


async def stream(
    strings,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    if not result:
        return

    from Opus.utils.api_logs import log_api
    def print(*args, **kwargs):
        msg = " ".join(str(arg) for arg in args)
        log_api(msg)

    is_video = bool(video)
    thumbnail = None

    if forceplay:
        await Signal.force_stop_stream(chat_id)

    if not strings or not isinstance(strings, dict) or "play_19" not in strings:
        from strings import get_string
        from Opus.utils.database import get_lang
        language = await get_lang(original_chat_id)
        strings = get_string(language)

    if streamtype == "playlist":
        msg = strings["play_19"] + "\n\n"
        count = 0
        
        # Calculate starting position for the whole playlist
        is_active = await is_active_chat(chat_id)
        current_pos = len(db.get(chat_id, [])) if is_active else 0

        for search in result:
            try:
                if isinstance(search, dict):
                    title = search.get("title", "Unknown")
                    vidid = search.get("vidid", "spotify")
                    duration_min = search.get("duration_min")
                    duration_sec = search.get("duration_sec")
                    thumbnail = search.get("thumb")
                    file_path = search.get("path")
                    performer = search.get("performer", "Aurex Music")

                    # Force fetch details from YouTube or Vortex if duration is missing (for personal playlists)
                    if not duration_min or str(duration_min) == "00:00":
                        if str(vidid).startswith("vortex_"):
                            try:
                                from Opus import Vortex
                                v_id = vidid.replace("vortex_", "")
                                v_details = await Vortex.details(v_id)
                                if v_details:
                                    title = v_details.get("title", title)
                                    duration_min = v_details.get("duration_min", "00:00")
                                    duration_sec = v_details.get("duration_sec", 0)
                                    thumbnail = v_details.get("thumb", thumbnail)
                                    file_path = v_details.get("path", file_path)
                                    performer = v_details.get("performer", performer)
                            except:
                                duration_min = "00:00"
                                duration_sec = 0
                        else:
                            try:
                                title_yt, dur_min, dur_sec, thumb, _, perf = await YouTube.details(vidid, True)
                                title = title_yt if not title or title == "Unknown" else title
                                duration_min = dur_min
                                duration_sec = dur_sec
                                thumbnail = thumb if not thumbnail else thumbnail
                                performer = perf if performer == "Aurex Music" else performer
                            except:
                                duration_min = "00:00"
                                duration_sec = 0
                else:
                    if str(search).startswith("vortex_"):
                        try:
                            from Opus import Vortex
                            v_id = str(search).replace("vortex_", "")
                            v_details = await Vortex.details(v_id)
                            title = v_details.get("title", "Unknown")
                            duration_min = v_details.get("duration_min", "00:00")
                            duration_sec = v_details.get("duration_sec", 0)
                            thumbnail = v_details.get("thumb")
                            file_path = v_details.get("path")
                            vidid = str(search)
                            performer = v_details.get("performer", "Vortex")
                        except:
                            continue
                    else:
                        title, duration_min, duration_sec, thumbnail, vidid, performer = await YouTube.details(
                            str(search), False if spotify else True
                        )
                        file_path = None
            except:
                continue
            if not duration_min or str(duration_min) == "None":
                continue
            if duration_sec > config.DURATION_LIMIT:
                continue

            # Force Spotify/Vortex tracks to be downloaded
            is_vortex = str(vidid).startswith("vortex_")

            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}" if is_vortex else (file_path if file_path else f"vid_{vidid}"),
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if is_video else "audio",
                    thumbnail=thumbnail,
                    performer=performer,
                )
                count += 1
                position = current_pos + (count - 1)
                msg += f"{count}. {str(title)[:70]}\n"
                msg += f"{strings['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                
                direct = True
                if is_vortex:
                    try:
                        from Opus.utils.downloader import download_url
                        await mystic.edit_text("<blockquote>📥 <b>ꜰᴇᴛᴄʜɪɴɢ ᴀᴜᴅɪᴏ...</b></blockquote>")
                        file_path = await download_url(file_path)
                        direct = False
                    except:
                        pass
                
                if not file_path:
                    if is_vortex:
                        raise AssistantErr(strings["play_14"])
                    try:
                        file_path, direct = await YouTube.download(
                            vidid, mystic, videoid=True, video=is_video, title=title, duration_sec=duration_sec
                        )
                    except:
                        raise AssistantErr(strings["play_14"])
                
                if not file_path:
                    raise AssistantErr(strings["play_14"])

                await Signal.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=is_video,
                    image=thumbnail,
                )
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if is_video else "audio",
                    forceplay=True,
                    thumbnail=thumbnail,
                    performer=performer,
                )
                
                count += 1
                position = 0
                msg += f"{count}. {str(title)[:70]}\n"
                msg += f"{strings['play_20']} 0\n\n"
                
                # After first song is joined, subsequent songs will start from position 1
                current_pos = 1 
                # We don't reset count here so numbering remains 1, 2, 3...
                
                # Robust localization check
                if not isinstance(strings, dict):
                    from strings import get_string
                    from Opus.utils.database import get_lang
                    strings = get_string(await get_lang(original_chat_id))

                if not direct:
                    from config import autoclean
                    autoclean.append(file_path)

                thumb_on = await get_thumb_setting(original_chat_id)
                from Opus.utils.database import is_on_playlist
                liked = await is_on_playlist(user_id, vidid)
                button = stream_markup(strings, vidid, chat_id, liked=liked)
                
                # Final safety check before formatting caption
                if not isinstance(strings, dict) or "stream_1" not in strings:
                    from strings import get_string
                    from Opus.utils.database import get_lang
                    strings = get_string(await get_lang(original_chat_id))

                caption = strings["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    str(title)[:23],
                    duration_min,
                    user_name,
                    performer,
                )
                if thumb_on:
                    if thumbnail and str(thumbnail).startswith("http"):
                        img = await get_thumb(vidid, force_url=thumbnail, force_title=title, chat_id=original_chat_id)
                    else:
                        img = await get_thumb(vidid, chat_id=original_chat_id)
                    run = await app.send_photo(
                        original_chat_id,
                        photo=img,
                        caption=caption,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_message(
                        original_chat_id,
                        text=caption,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                if chat_id in db and len(db[chat_id]) > 0:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

        if count == 0:
            return
        else:
            link = await SignalBin(msg)
            lines = msg.count("\n")
            if lines >= 100:
                car = os.linesep.join(msg.split(os.linesep)[:100]) + "\n..."
            else:
                car = msg
            first_thumb = None
            first_vidid = None
            if isinstance(result, list) and len(result) > 0:
                first = result[0]
                if isinstance(first, dict):
                    first_thumb = first.get("thumb")
                    first_vidid = first.get("vidid")
                else:
                    # If it's just a search string, we don't have details yet
                    pass

            carbon = await gen_qthumb(car, randint(100, 10000000), videoid=first_vidid, thumbnail_url=first_thumb)
            upl = close_markup(strings)
            return await app.send_photo(
                original_chat_id,
                photo=carbon,
                caption=strings["play_21"].format(position, link),
                reply_markup=upl,
            )

    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]
        performer = result.get("performer", "YouTube")

        file_path = result.get("path")
        direct = True
        duration_sec = result.get("duration_sec") or 0
        if not file_path:
            # Retry loop: CDN backends often cache tracks after the first request,
            # so a second attempt after a short delay almost always succeeds.
            import asyncio as _asyncio
            import aiofiles as _aiofiles
            import os as _os
            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                # Resolve a download URL via our multi-source resolver
                n, link_direct = await YouTube.video(vidid, is_video=is_video, title=title)
                if n == 2:
                    # Already a local file — use it directly
                    file_path = link_direct
                    direct = False
                    break
                elif n == 1:
                    # Got a remote URL — download it locally to prevent auto-end
                    print(f"[stream] Got streamable URL for {vidid}, downloading locally to prevent auto-end...")
                    ext = "mp4" if is_video else "mp3"
                    local_path = f"downloads/{vidid}.{ext}"
                    _os.makedirs("downloads", exist_ok=True)
                    # Check if already downloaded
                    if _os.path.exists(local_path) and _os.path.getsize(local_path) > 10240:
                        file_path = local_path
                        direct = False
                        break
                    else:
                        try:
                            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as dl_client:
                                async with dl_client.stream("GET", link_direct, timeout=60) as resp:
                                    if resp.status_code == 200:
                                        async with _aiofiles.open(local_path, "wb") as f:
                                            async for chunk in resp.aiter_bytes(8 * 1024 * 1024):
                                                if chunk:
                                                    await f.write(chunk)
                            if _os.path.exists(local_path) and _os.path.getsize(local_path) > 10240:
                                print(f"[stream] Downloaded locally: {local_path} ({_os.path.getsize(local_path)} bytes)")
                                file_path = local_path
                                direct = False
                                break
                            else:
                                print(f"[stream] Local download too small, falling back to URL stream...")
                                file_path = link_direct
                                direct = True
                                break
                        except Exception as dl_err:
                            print(f"[stream] Local download failed ({dl_err}), falling back to URL stream...")
                            file_path = link_direct
                            direct = True
                            break
                else:
                    # All resolvers failed
                    if attempt < max_attempts:
                        print(f"[stream] Attempt {attempt} failed for {vidid}. Retrying in 2s...")
                        await _asyncio.sleep(2)
                        continue
                    # Final attempt — try YouTube.download() as last resort
                    try:
                        print(f"[stream] All resolve attempts failed. Trying YouTube.download for: {vidid}...")
                        file_path, direct = await YouTube.download(
                            vidid, mystic, videoid=True, video=is_video, title=title, duration_sec=duration_sec
                        )
                    except Exception as e:
                        print(f"[stream] YouTube.download failed for {vidid} with exception: {e}")
                        raise AssistantErr(strings["play_14"])
        if not file_path:
            raise AssistantErr(strings["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                thumbnail=thumbnail,
                performer=performer,
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(strings, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=strings["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []

            # Start playback and thumbnail generation concurrently
            # so the user hears music ASAP while the thumbnail renders
            import asyncio as _asyncio

            thumb_on = await get_thumb_setting(original_chat_id)

            async def _generate_thumb():
                if thumb_on:
                    if thumbnail and thumbnail.startswith("http"):
                        return await get_thumb(vidid, force_url=thumbnail, force_title=title, chat_id=original_chat_id)
                    else:
                        return await get_thumb(vidid, chat_id=original_chat_id)
                return None

            # Fire both tasks at once: join call + generate thumbnail
            thumb_task = _asyncio.ensure_future(_generate_thumb())

            # Try to join with the file_path (could be URL or local)
            try:
                await Signal.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=is_video,
                    image=thumbnail,
                )
            except Exception as join_err:
                # If direct URL streaming failed, download and retry
                if file_path.startswith("http"):
                    try:
                        if mystic:
                            await mystic.edit_text("<blockquote>📥 <b>ꜰᴇᴛᴄʜɪɴɢ ᴀᴜᴅɪᴏ...</b></blockquote>")
                        file_path, direct = await YouTube.download(
                            vidid, mystic, videoid=True, video=is_video, title=title, duration_sec=duration_sec
                        )
                        if not file_path:
                            raise AssistantErr(strings["play_14"])
                        direct = False
                        from config import autoclean
                        if file_path not in autoclean:
                            autoclean.append(file_path)
                        await Signal.join_call(
                            chat_id,
                            original_chat_id,
                            file_path,
                            video=is_video,
                            image=thumbnail,
                        )
                    except AssistantErr:
                        raise
                    except Exception:
                        raise AssistantErr(strings["play_14"])
                else:
                    raise

            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
                thumbnail=thumbnail,
            )

            from Opus.utils.database import is_on_playlist
            liked = await is_on_playlist(user_id, vidid)
            button = stream_markup(strings, vidid, chat_id, liked=liked)
            caption = strings["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23],
                duration_min,
                user_name, performer
            )

            # Now wait for thumbnail (may already be done)
            img = await thumb_task

            if thumb_on and img:
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    original_chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            if chat_id in db and len(db[chat_id]) > 0:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(strings, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=strings["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Signal.join_call(chat_id, original_chat_id, file_path, video=False)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
                forceplay=forceplay,
            )
            thumb_on = await get_thumb_setting(original_chat_id)
            button = stream_markup(strings, streamtype, chat_id)
            caption = strings["stream_1"].format(
                config.SUPPORT_CHAT, title[:23], duration_min, user_name, "SoundCloud"
            )
            if thumb_on:
                run = await app.send_photo(
                    original_chat_id,
                    photo=config.SOUNCLOUD_IMG_URL,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    original_chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            if chat_id in db and len(db[chat_id]) > 0:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video else "audio",
                thumbnail=thumbnail,
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(strings, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=strings["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Signal.join_call(chat_id, original_chat_id, file_path, video=is_video)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
                thumbnail=thumbnail,
            )
            if is_video:
                await add_active_video_chat(chat_id)
            thumb_on = await get_thumb_setting(original_chat_id)
            button = stream_markup(strings, streamtype, chat_id)
            caption = strings["stream_1"].format(link, title[:23], duration_min, user_name, "Telegram")
            thumb_photo = config.TELEGRAM_VIDEO_URL if is_video else config.TELEGRAM_AUDIO_URL
            if thumb_on:
                run = await app.send_photo(
                    original_chat_id,
                    photo=thumb_photo,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    original_chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            if chat_id in db and len(db[chat_id]) > 0:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        thumbnail = result["thumb"]
        duration_min = "Live Track"

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                thumbnail=thumbnail,
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(strings, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=strings["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            n, file_path = await YouTube.video(link, is_video=is_video, title=title)
            if n in (0, None) or not file_path:
                raise AssistantErr(strings["str_3"])
            
            # If n=2, it's a local file, so we mark it for autoclean
            if n == 2:
                from config import autoclean
                if file_path not in autoclean:
                    autoclean.append(file_path)
            await Signal.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=is_video,
                image=thumbnail if thumbnail else None,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
                thumbnail=thumbnail,
            )
            thumb_on = await get_thumb_setting(original_chat_id)
            from Opus.utils.database import is_on_playlist
            liked = await is_on_playlist(user_id, vidid)
            button = stream_markup(strings, vidid, chat_id, liked=liked)
            caption = strings["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23],
                duration_min,
                user_name, "YouTube Live"
            )
            if thumb_on:
                if thumbnail and thumbnail.startswith("http"):
                    img = await get_thumb(vidid, force_url=thumbnail, force_title=title, chat_id=original_chat_id)
                else:
                    img = await get_thumb(vidid, chat_id=original_chat_id)
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    original_chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            if chat_id in db and len(db[chat_id]) > 0:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

    elif streamtype == "index":
        link = result
        title = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ"
        duration_min = "00:00"

        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
                thumbnail=thumbnail,
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(strings, chat_id)
            await mystic.edit_text(
                text=strings["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await Signal.join_call(
                chat_id,
                original_chat_id,
                link,
                video=is_video,
            )
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if is_video else "audio",
                forceplay=forceplay,
                thumbnail=thumbnail,
            )
            thumb_on = await get_thumb_setting(original_chat_id)
            button = stream_markup(strings, "index_url", chat_id)
            caption = strings["stream_2"].format(user_name)
            if thumb_on:
                run = await app.send_photo(
                    original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    original_chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            if chat_id in db and len(db[chat_id]) > 0:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            await mystic.delete()

    elif streamtype == "vortex":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]
        performer = result.get("performer", "Spotify")

        file_path = result.get("path")
        direct = True
        
        # Download Spotify tracks locally to prevent expiry/freezes
        if file_path and file_path.startswith("http"):
            await mystic.edit_text("<blockquote>📥 <b>ꜰᴇᴛᴄʜɪɴɢ ᴀᴜᴅɪᴏ...</b></blockquote>")
            try:
                from Opus.utils.downloader import download_url
                local_path = await download_url(file_path)
                if local_path:
                    file_path = local_path
                    direct = False
            except Exception as e:
                print(f"Spotify Download Error: {e}")
                # Fallback to direct URL if download fails
                pass

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                thumbnail=thumbnail,
                performer=performer,
            )
            # Ensure local file is cleaned up later
            if not direct:
                from config import autoclean
                autoclean.append(file_path)

            position = len(db.get(chat_id)) - 1
            button = aq_markup(strings, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=strings["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            
            await Signal.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=is_video,
                image=thumbnail,
            )
            
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if is_video else "audio",
                forceplay=forceplay,
                thumbnail=thumbnail,
                performer=performer,
            )
            # Ensure local file is cleaned up later
            if not direct:
                from config import autoclean
                autoclean.append(file_path)

            thumb_on = await get_thumb_setting(original_chat_id)
            from Opus.utils.database import is_on_playlist
            liked = await is_on_playlist(user_id, vidid)
            button = stream_markup(strings, vidid, chat_id, liked=liked)
            caption = strings["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{vidid}",
                title[:23],
                duration_min,
                user_name, performer
            )
            if thumb_on:
                if thumbnail and thumbnail.startswith("http"):
                    img = await get_thumb(vidid, force_url=thumbnail, force_title=title, chat_id=original_chat_id)
                else:
                    img = await get_thumb(vidid, chat_id=original_chat_id)
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    original_chat_id,
                    text=caption,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            if chat_id in db and len(db[chat_id]) > 0:
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
            await mystic.delete()
