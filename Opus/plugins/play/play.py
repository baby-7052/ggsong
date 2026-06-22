import asyncio
import os
import random
import string
import traceback

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message
from pyrogram.errors.exceptions.bad_request_400 import MessageIdInvalid
from pytgcalls.exceptions import NoActiveGroupCall

import config
from Opus import Apple, Resso, SoundCloud, Spotify, Telegram, YouTube, Vortex, app
from Opus.core.call import Signal
from Opus.misc import db
from Opus.utils import seconds_to_min, time_to_seconds
from Opus.utils.channelplay import get_channeplayCB
from Opus.utils.decorators.language import languageCB
from Opus.utils.decorators.play import PlayWrapper
from Opus.utils.database import (
    autoplay_off,
    autoplay_on,
    get_lang,
    get_playtype,
    is_autoplay,
)
from Opus.utils.admin_check import is_admin
from Opus.utils.formatters import formats
from Opus.utils.inline import (
    botplaylist_markup,
    livestream_markup,
    playlist_markup,
    slider_markup,
    stream_markup,
    stream_markup_autoplay,
    track_markup,
    upnext_markup,
)
from Opus.utils.logger import play_logs
from Opus.utils.stream.stream import stream
from Opus.utils.downloader import download_audio, safe_filename
from Opus.utils.security import is_malicious, report_security_breach
from config import BANNED_USERS, lyrical, OWNER_ID
from Opus.misc import SUDOERS

sticker_id = "CAACAgUAAxkBAAIe72mqfmL7cPOdiA5TOr6Gsih09cVTAALgGQACfA2YVRl1rlBfNwT5HgQ"


async def safe_edit_or_send(message: Message, msg_obj: Message, text: str):
    try:
        return await msg_obj.edit_text(text)
    except MessageIdInvalid:
        return await message.reply_text(text)
    except Exception as e:
        try:
            return await message.reply_text(text)
        except:
            print(f"Failed to send message: {e}")
            return None

@app.on_message(
    filters.command(
        [
            "play",
            "vplay",
            "cplay",
            "cvplay",
            "playforce",
            "vplayforce",
            "cplayforce",
            "cvplayforce",
        ],
        prefixes=[".", "!", "/"],
    )
    & filters.group
    & ~BANNED_USERS
)
@PlayWrapper
async def play_commnd(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    # Security check for malicious queries
    check_text = url or (message.text.split(None, 1)[1] if len(message.command) > 1 else "")
    if is_malicious(check_text):
        await report_security_breach(client, message, check_text)
        return await message.reply_text(
            "<blockquote><b>⚠️ SECURITY ALERT</b>\n\n"
            "ʏᴏᴜʀ ǫᴜᴇʀʏ ʜᴀs ʙᴇᴇɴ ғʟᴀɢɢᴇᴅ ᴀs ᴘᴏᴛᴇɴᴛɪᴀʟʟʏ ᴍᴀʟɪᴄɪᴏᴜs ᴀɴᴅ ʀᴇᴘᴏʀᴛᴇᴅ ᴛᴏ ᴛʜᴇ ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs.\n"
            "ᴀᴛᴛᴇᴍᴘᴛɪɴɢ ᴛᴏ ᴇxᴘʟᴏɪᴛ ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ʀᴇsᴜʟᴛ ɪɴ ᴀ ɢʟᴏʙᴀʟ ʙᴀɴ.</blockquote>"
        )

    mystic = await message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    plist_id = None
    slider = None
    plist_type = None
    spotify = None
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    audio_telegram = (
        (message.reply_to_message.audio or message.reply_to_message.voice)
        if message.reply_to_message
        else None
    )
    video_telegram = (
        (message.reply_to_message.video or message.reply_to_message.document)
        if message.reply_to_message
        else None
    )

    if audio_telegram:
        if audio_telegram.file_size > 104857600:
            return await safe_edit_or_send(message, mystic, _["play_5"])
        duration_min = seconds_to_min(audio_telegram.duration)
        if audio_telegram.duration > config.DURATION_LIMIT:
            return await safe_edit_or_send(
                message,
                mystic,
                _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention),
            )
        file_path = await Telegram.get_filepath(audio=audio_telegram)
        if not file_path:
            return await safe_edit_or_send(message, mystic, _["play_3"])
        ok = await Telegram.download(_, message, mystic, file_path)
        if not ok or not os.path.exists(file_path):
            return await safe_edit_or_send(message, mystic, _["play_3"])
        message_link = await Telegram.get_link(message)
        file_name = await Telegram.get_filename(audio_telegram, audio=True)
        dur = await Telegram.get_duration(audio_telegram, file_path)
        details = {
            "title": file_name,
            "link": message_link,
            "path": file_path,
            "dur": dur,
        }
        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                streamtype="telegram",
                forceplay=fplay,
            )
        except Exception:
            traceback.print_exc()
            return await safe_edit_or_send(message, mystic, _["play_3"])
        try:
            return await mystic.delete()
        except:
            return

    elif video_telegram:
        if message.reply_to_message.document:
            try:
                ext = video_telegram.file_name.split(".")[-1]
                if ext.lower() not in formats:
                    return await safe_edit_or_send(
                        message, mystic, _["play_7"].format(f"{' | '.join(formats)}")
                    )
            except:
                return await safe_edit_or_send(
                    message, mystic, _["play_7"].format(f"{' | '.join(formats)}")
                )
        if video_telegram.file_size > config.TG_VIDEO_FILESIZE_LIMIT:
            return await safe_edit_or_send(message, mystic, _["play_8"])
        file_path = await Telegram.get_filepath(video=video_telegram)
        if not file_path:
            return await safe_edit_or_send(message, mystic, _["play_3"])
        ok = await Telegram.download(_, message, mystic, file_path)
        if not ok or not os.path.exists(file_path):
            return await safe_edit_or_send(message, mystic, _["play_3"])
        message_link = await Telegram.get_link(message)
        file_name = await Telegram.get_filename(video_telegram)
        dur = await Telegram.get_duration(video_telegram, file_path)
        details = {
            "title": file_name,
            "link": message_link,
            "path": file_path,
            "dur": dur,
        }
        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=True,
                streamtype="telegram",
                forceplay=fplay,
            )
        except Exception:
            traceback.print_exc()
            return await safe_edit_or_send(message, mystic, _["play_3"])
        try:
            return await mystic.delete()
        except:
            return

    elif url:
        if await YouTube.exists(url):
            if "playlist" in url:
                try:
                    details = await YouTube.playlist(
                        url,
                        config.PLAYLIST_FETCH_LIMIT,
                        message.from_user.id,
                    )
                except:
                    return await safe_edit_or_send(message, mystic, _["play_3"])
                streamtype = "playlist"
                plist_type = "yt"
                if "&" in url:
                    plist_id = (url.split("=")[1]).split("&")[0]
                else:
                    plist_id = url.split("=")[1]
                img = config.PLAYLIST_IMG_URL
                cap = _["play_9"]
            else:
                try:
                    details, track_id = await YouTube.track(url)
                except:
                    return await safe_edit_or_send(message, mystic, _["play_3"])
                streamtype = "youtube"
                img = details.get("thumb", "")
                duration_min = details.get("duration_min", "Unknown")
                cap = _["play_10"].format(details.get("title", "Unknown"), duration_min)

        elif await Spotify.valid(url):
            spotify = True
            if "track" in url:
                try:
                    details, track_id = await Spotify.track(url)
                except:
                    return await safe_edit_or_send(message, mystic, _["play_3"])
                streamtype = "youtube"
                img = details.get("thumb", "")
                duration_min = details.get("duration_min", "Unknown")
                cap = _["play_10"].format(details.get("title", "Unknown"), duration_min)
            elif "playlist" in url:
                try:
                    details, plist_id = await Spotify.playlist(url)
                except Exception:
                    return await safe_edit_or_send(message, mystic, _["play_3"])
                streamtype = "playlist"
                plist_type = "spplay"
                img = config.SPOTIFY_PLAYLIST_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
            elif "album" in url:
                try:
                    details, plist_id = await Spotify.album(url)
                except:
                    return await safe_edit_or_send(message, mystic, _["play_3"])
                streamtype = "playlist"
                plist_type = "spalbum"
                img = config.SPOTIFY_ALBUM_IMG_URL
                cap = _["play_11"].format(app.mention, message.from_user.mention)
            elif "artist" in url:
                try:
                    details, plist_id = await Spotify.artist(url)
                except:
                    return await safe_edit_or_send(message, mystic, _["play_3"])
                streamtype = "playlist"
                plist_type = "spartist"
                img = config.SPOTIFY_ARTIST_IMG_URL
                cap = _["play_11"].format(message.from_user.first_name)
            else:
                return await safe_edit_or_send(message, mystic, _["play_15"])

        elif await Apple.valid(url):
            if "album" in url:
                try:
                    details, track_id = await Apple.track(url)
                except:
                    return await safe_edit_or_send(message, mystic, _["play_3"])
                streamtype = "youtube"
                img = details.get("thumb", "")
                duration_min = details.get("duration_min", "Unknown")
                cap = _["play_10"].format(details.get("title", "Unknown"), duration_min)
            elif "playlist" in url:
                spotify = True
                try:
                    details, plist_id = await Apple.playlist(url)
                except:
                    return await safe_edit_or_send(message, mystic, _["play_3"])
                streamtype = "playlist"
                plist_type = "apple"
                cap = _["play_12"].format(app.mention, message.from_user.mention)
                img = url
            else:
                return await safe_edit_or_send(message, mystic, _["play_3"])

        elif await Resso.valid(url):
            try:
                details, track_id = await Resso.track(url)
            except:
                return await safe_edit_or_send(message, mystic, _["play_3"])
            streamtype = "youtube"
            img = details.get("thumb", "")
            duration_min = details.get("duration_min", "Unknown")
            cap = _["play_10"].format(details.get("title", "Unknown"), duration_min)

        elif await SoundCloud.valid(url):
            try:
                details, track_path = await SoundCloud.download(url)
            except:
                return await safe_edit_or_send(message, mystic, _["play_3"])
            if not track_path or not os.path.exists(str(track_path)):
                return await safe_edit_or_send(message, mystic, _["play_3"])
            duration_sec = details.get("duration_sec", 0)
            if duration_sec > config.DURATION_LIMIT:
                return await safe_edit_or_send(
                    message,
                    mystic,
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        app.mention,
                    ),
                )
            details["filepath"] = track_path
            try:
                await stream(
                    _,
                    mystic,
                    user_id,
                    details,
                    chat_id,
                    user_name,
                    message.chat.id,
                    streamtype="soundcloud",
                    forceplay=fplay,
                )
            except Exception:
                traceback.print_exc()
                return await safe_edit_or_send(message, mystic, _["play_3"])
            try:
                return await mystic.delete()
            except:
                return

        else:
            try:
                await Signal.stream_call(url)
            except NoActiveGroupCall:
                await safe_edit_or_send(message, mystic, _["black_9"])
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=_["play_17"],
                )
            except Exception:
                traceback.print_exc()
                return await safe_edit_or_send(message, mystic, _["play_3"])
            await safe_edit_or_send(message, mystic, _["str_2"])
            try:
                await stream(
                    _,
                    mystic,
                    message.from_user.id,
                    url,
                    chat_id,
                    message.from_user.first_name,
                    message.chat.id,
                    video=video,
                    streamtype="index",
                    forceplay=fplay,
                )
            except Exception:
                traceback.print_exc()
                return await safe_edit_or_send(message, mystic, _["play_3"])
            return await play_logs(message, streamtype="M3u8 or Index Link")

    else:
        if len(message.command) < 2:
            buttons = botplaylist_markup(_)
            return await safe_edit_or_send(message, mystic, _["play_18"])
        slider = True
        query = message.text.split(None, 1)[1]
        if "-v" in query:
            query = query.replace("-v", "")
        try:
            details, track_id = await YouTube.track(query)
        except:
            return await safe_edit_or_send(message, mystic, _["play_3"])
        streamtype = "youtube"

    if str(playmode) == "Direct":
        if not plist_type:
            if details and details.get("duration_min"):
                duration_sec = time_to_seconds(details["duration_min"])
                if duration_sec > config.DURATION_LIMIT:
                    return await safe_edit_or_send(
                        message,
                        mystic,
                        _["play_6"].format(
                            config.DURATION_LIMIT_MIN,
                            app.mention,
                        ),
                    )
            else:
                buttons = livestream_markup(
                    _,
                    track_id,
                    user_id,
                    "v" if video else "a",
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                try:
                    await mystic.edit_text(
                        _["play_13"],
                        reply_markup=InlineKeyboardMarkup(buttons),
                    )
                except MessageIdInvalid:
                    await message.reply_text(
                        _["play_13"],
                        reply_markup=InlineKeyboardMarkup(buttons),
                    )
                return
        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=video,
                streamtype=streamtype,
                spotify=spotify,
                forceplay=fplay,
            )
        except Exception as e:
            if type(e).__name__ == "AssistantErr":
                return await safe_edit_or_send(message, mystic, str(e))
            traceback.print_exc()
            return await safe_edit_or_send(message, mystic, _["play_3"])
        try:
            await mystic.delete()
        except:
            pass
        return await play_logs(message, streamtype=streamtype)

    else:
        if plist_type:
            ran_hash = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
            lyrical[ran_hash] = plist_id
            buttons = playlist_markup(
                _,
                ran_hash,
                message.from_user.id,
                plist_type,
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            try:
                await mystic.delete()
            except:
                pass
            await message.reply_photo(
                photo=img,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return await play_logs(message, streamtype=f"Playlist : {plist_type}")
        else:
            if slider:
                buttons = slider_markup(
                    _,
                    track_id,
                    message.from_user.id,
                    query,
                    0,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                try:
                    await mystic.delete()
                except:
                    pass
                await message.reply_photo(
                    photo=details.get("thumb", ""),
                    caption=_["play_10"].format(
                        details.get("title", "Unknown").title(),
                        details.get("duration_min", "Unknown"),
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype="Searched on Youtube")
            else:
                buttons = track_markup(
                    _,
                    track_id,
                    message.from_user.id,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                try:
                    await mystic.delete()
                except:
                    pass
                await message.reply_photo(
                    photo=img,
                    caption=cap,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype="URL Searched Inline")

@app.on_callback_query(filters.regex("MusicStream") & ~BANNED_USERS)
@languageCB
async def play_music(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    vidid, user_id, mode, cplay, fplay = callback_request.split("|")
    if int(user_id) == 0:
        # Check playmode for suggestions
        chat_id = CallbackQuery.message.chat.id
        play_mode = await get_playtype(chat_id)
        if play_mode != "Everyone":
            if not await is_admin(CallbackQuery):
                return await CallbackQuery.answer("ʀᴇsᴛʀɪᴄᴛᴇᴅ: ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴘʟᴀʏ ғʀᴏᴍ sᴜɢɢᴇsᴛɪᴏɴs!", show_alert=True)
    elif CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    user_name = CallbackQuery.from_user.first_name
    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except:
        pass
    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None

    # Vortex Support
    if str(vidid).startswith("vortex_"):
        v_id = vidid.replace("vortex_", "")
        details = await Vortex.details(v_id)
        if not details:
            return await mystic.edit_text(_["play_3"])
        
        if details.get("duration_min"):
            duration_sec = details.get("duration_sec", 0)
            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
                )

        try:
            await stream(
                _,
                mystic,
                CallbackQuery.from_user.id,
                details,
                chat_id,
                user_name,
                CallbackQuery.message.chat.id,
                video,
                streamtype="vortex",
                forceplay=ffplay,
            )
        except Exception:
            traceback.print_exc()
            return await mystic.edit_text(_["play_3"])
        return await mystic.delete()

    # YouTube Support
    try:
        details, track_id = await YouTube.track(vidid, True)
    except:
        return await mystic.edit_text(_["play_3"])
        
    if details["duration_min"]:
        duration_sec = time_to_seconds(details["duration_min"])
        if duration_sec > config.DURATION_LIMIT:
            return await mystic.edit_text(
                _["play_6"].format(config.DURATION_LIMIT_MIN, app.mention)
            )
    else:
        buttons = livestream_markup(
            _,
            track_id,
            CallbackQuery.from_user.id,
            mode,
            "c" if cplay == "c" else "g",
            "f" if fplay else "d",
        )
        return await mystic.edit_text(
            _["play_13"],
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    try:
        await stream(
            _,
            mystic,
            CallbackQuery.from_user.id,
            details,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="youtube",
            forceplay=ffplay,
        )
    except Exception:
        traceback.print_exc()
        return await mystic.edit_text(_["play_3"])
    return await mystic.delete()


@app.on_callback_query(filters.regex("SignalmousAdmin") & ~BANNED_USERS)
async def Signalmous_check(client, CallbackQuery):
    try:
        await CallbackQuery.answer(
            "» ʀᴇᴠᴇʀᴛ ʙᴀᴄᴋ ᴛᴏ ᴜsᴇʀ ᴀᴄᴄᴏᴜɴᴛ :\n\nᴏᴘᴇɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ sᴇᴛᴛɪɴɢs.\n-> ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀs\n-> ᴄʟɪᴄᴋ ᴏɴ ʏᴏᴜʀ ɴᴀᴍᴇ\n-> ᴜɴᴄʜᴇᴋ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.",
            show_alert=True,
        )
    except:
        pass


# Active downloads tracker to prevent concurrent saves per user
ACTIVE_DOWNLOADS = set()

@app.on_callback_query(filters.regex("SaveStream") & ~BANNED_USERS)
@languageCB
async def save_track_cb(client, CallbackQuery, _):
    user_id = CallbackQuery.from_user.id
    from Opus.utils.downloader import DOWNLOAD_PROGRESS
    if user_id in ACTIVE_DOWNLOADS:
        percent = DOWNLOAD_PROGRESS.get(user_id, 0)
        return await CallbackQuery.answer(
            f"» ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ʜᴀᴠᴇ ᴀɴ ᴀᴄᴛɪᴠᴇ ᴅᴏᴡɴʟᴏᴀᴅ.\n\nɪᴛ ɪs ᴄᴜʀʀᴇɴᴛʟʏ {percent}% ᴅᴏɴᴇ! ⏳",
            show_alert=True
        )
        
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    videoid = callback_request
    if videoid in ["telegram", "soundcloud", "index_url"]:
        return await CallbackQuery.answer("sᴏʀʀʏ, ᴄᴀɴ'ᴛ sᴀᴠᴇ ᴛʜɪs ᴛʀᴀᴄᴋ !!", show_alert=True)
        
    ACTIVE_DOWNLOADS.add(user_id)
    DOWNLOAD_PROGRESS[user_id] = 0
    try:
        await CallbackQuery.answer("ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ᴛʀᴀᴄᴋ... 📥")
        
        title, duration, thumb, path, performer = None, None, None, None, "Aurex Music"

        if videoid.startswith("vortex_"):
            try:
                v_id = videoid.replace("vortex_", "")
                details = await Vortex.details(v_id)
                if details:
                    title = details.get("title")
                    duration = details.get("duration_min")
                    thumb = details.get("thumb")
                    path = details.get("path")
                    performer = details.get("performer", "Vortex")
            except Exception as e:
                print(f"Vortex Save Error: {e}")

        duration_sec = 0
        if not title:
            try:
                title, duration, duration_sec, thumb, _, performer = await YouTube.details(videoid)
            except:
                title, duration = "Unknown", "Unknown"
        else:
            # If title was already found (e.g. from Vortex), try to get duration_sec if missing
            if not duration_sec and "duration_sec" in locals().get("details", {}):
                duration_sec = details.get("duration_sec", 0)

        try:
            # download_audio now handles direct URLs if path is passed
            file_path = await download_audio(path if path else videoid, title=title, duration_sec=duration_sec, user_id=user_id)
        except Exception as e:
            return await CallbackQuery.message.reply_text(f"ғᴀɪʟᴇᴅ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ᴛʀᴀᴄᴋ.\nᴇʀʀᴏʀ: {e}")
        
        if not file_path or not os.path.exists(file_path):
            return await CallbackQuery.message.reply_text("ғᴀɪʟᴇᴅ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ᴛʀᴀᴄᴋ.")

        # Rename file to song title
        new_path = os.path.join("downloads", f"{safe_filename(title)}.mp3")
        try:
            if os.path.exists(new_path):
                os.remove(new_path)
            os.rename(file_path, new_path)
            file_path = new_path
        except Exception as e:
            print(f"Rename Error: {e}")

        # Use HTML tags as requested
        caption = (
            f"<blockquote><b>﹝  ʙɪxʏ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ  ﹞</b></blockquote>\n"
            f"<blockquote><b>{str(title)[:35]}</b></blockquote>\n"
            f"<blockquote><b>ʙʏ : @{app.username}</b></blockquote>"
        )

        # Download thumbnail if it's a URL
        thumb_path = None
        if thumb and thumb.startswith("http"):
            try:
                from Opus.utils.downloader import download_url
                thumb_path = await download_url(thumb)
            except Exception as e:
                print(f"Thumb Download Error: {e}")

        # Apply permanent metadata tags and thumbnail using FFmpeg
        try:
            from Opus.utils.downloader import apply_metadata
            await apply_metadata(file_path, title, performer, thumb_path)
        except Exception as e:
            print(f"Apply Metadata Error: {e}")

        # Send the Audio file as a direct reply to the original message
        try:
            await CallbackQuery.message.reply_audio(
                audio=file_path,
                caption=caption,
                thumb=thumb_path if (thumb_path and os.path.exists(thumb_path)) else None,
                performer=str(performer),
                title=str(title),
                duration=duration_sec,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Bɪxy", url="https://t.me/Usebixy")]]
                ),
            )
        except Exception as e:
            await CallbackQuery.message.reply_text(f"ғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ᴀᴜᴅɪᴏ.\nᴇʀʀᴏʀ: {e}")
        
        if os.path.exists(file_path):
            os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
    finally:
        ACTIVE_DOWNLOADS.discard(user_id)
        DOWNLOAD_PROGRESS.pop(user_id, None)


@app.on_callback_query(filters.regex("LyricsStream") & ~BANNED_USERS)
@languageCB
async def lyrics_stream_cb(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    videoid = callback_data.split(None, 1)[1]
    
    await CallbackQuery.answer("ғᴇᴛᴄʜɪɴɢ ʟʏʀɪᴄs... 🎤")
    
    chat_id = CallbackQuery.message.chat.id
    playing = db.get(chat_id)
    title = None
    lyrics_text = None

    # 1. Try to use cached lyrics from background fetcher
    if playing and playing[0].get("vidid") == videoid:
        title = playing[0].get("title")
        synced = playing[0].get("synced_lyrics")
        plain = playing[0].get("plain_lyrics")
        
        if synced and isinstance(synced, list):
            # Format synced lyrics for plain display
            lyrics_text = "\n".join([line for _, line in synced])
        elif isinstance(synced, str):
            lyrics_text = synced
        elif plain:
            lyrics_text = plain
    
    # 2. If not cached, extract title and search
    if not lyrics_text:
        if not title:
            # Fallback title extraction
            msg_text = CallbackQuery.message.caption or CallbackQuery.message.text
            if msg_text:
                for line in msg_text.split("\n"):
                    clean_line = line.strip().replace("•", "").replace("<b>", "").replace("</b>", "").replace("<blockquote>", "").replace("</blockquote>", "").strip()
                    clean_line = clean_line.replace("❞", "").replace("❝", "").strip(" |").strip()
                    
                    if not clean_line or "[" in clean_line or "]" in clean_line:
                        continue
                    if clean_line.startswith("-") or clean_line.startswith("—") or (" - " in clean_line and len(clean_line.split(" - ")[0]) < 5):
                        continue
                        
                    title = clean_line
                    break

    if not lyrics_text:
        if not title or title == "Unknown":
            try:
                from Opus.platforms.Youtube import YouTube
                title, _, _, _, _, _ = await YouTube.details(videoid)
            except:
                title = "Unknown"

        # AGGRESSIVE CLEANING: Remove YouTube noise
        search_title = title
        if " | " in search_title:
            search_title = search_title.split(" | ")[0]
        if " - " in search_title:
            search_title = search_title.split(" - ")[0]
        search_title = search_title.split("(")[0].split("[")[0].strip()

        from Opus.platforms.Lyrics import Lyrics
        # Try Synced search first
        synced_res = await Lyrics.get_synced_lyrics(search_title)
        if synced_res and isinstance(synced_res, list):
            lyrics_text = "\n".join([line for _, line in synced_res])
        elif isinstance(synced_res, str):
            lyrics_text = synced_res
        else:
            # Final fallback to plain
            lyrics_text = await Lyrics.get_lyrics(search_title)
    
    if not lyrics_text:
        return await CallbackQuery.message.reply_text(f"ɴᴏ ʟʏʀɪᴄs ғᴏᴜɴᴅ ғᴏʀ <b>{title}</b>.")
    
    # Send lyrics in a box
    await CallbackQuery.message.reply_text(
        f"🎤 <b>LYRICS FOR {title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"<blockquote>{lyrics_text}</blockquote>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(_["CLOSE_BUTTON"], callback_data="close")]]
        )
    )
    



@app.on_callback_query(filters.regex("SignalPlaylists") & ~BANNED_USERS)
@languageCB
async def play_playlists_command(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        videoid,
        user_id,
        ptype,
        mode,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    user_name = CallbackQuery.from_user.first_name
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except:
        pass
    mystic = await CallbackQuery.message.reply_text(
        _["play_2"].format(channel) if channel else _["play_1"]
    )
    videoid = lyrical.get(videoid)
    video = True if mode == "v" else None
    ffplay = True if fplay == "f" else None
    spotify = True
    if ptype == "yt":
        spotify = False
        try:
            result = await YouTube.playlist(
                videoid,
                config.PLAYLIST_FETCH_LIMIT,
                CallbackQuery.from_user.id,
                True,
            )
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spplay":
        try:
            result, spotify_id = await Spotify.playlist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "spalbum":
        try:
            result, spotify_id = await Spotify.album(videoid)
        except:
            return await mystic.edit_text(_["play_3"])


    if ptype == "spartist":
        try:
            result, spotify_id = await Spotify.artist(videoid)
        except:
            return await mystic.edit_text(_["play_3"])
    if ptype == "apple":
        try:
            result, apple_id = await Apple.playlist(videoid, True)
        except:
            return await mystic.edit_text(_["play_3"])
    try:
        await stream(
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="playlist",
            spotify=spotify,
            forceplay=ffplay,
        )
    except Exception:
        traceback.print_exc()
        return await mystic.edit_text(_["play_3"])
    return await mystic.delete()


@app.on_callback_query(filters.regex("slider") & ~BANNED_USERS)
@languageCB
async def slider_queries(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    (
        what,
        rtype,
        query,
        user_id,
        cplay,
        fplay,
    ) = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return
    what = str(what)
    rtype = int(rtype)
    if what == "F":
        if rtype == 9:
            query_type = 0
        else:
            query_type = int(rtype + 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(
            media=thumbnail,
            caption=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med, reply_markup=InlineKeyboardMarkup(buttons)
        )
    if what == "B":
        if rtype == 0:
            query_type = 9
        else:
            query_type = int(rtype - 1)
        try:
            await CallbackQuery.answer(_["playcb_2"])
        except:
            pass
        title, duration_min, thumbnail, vidid = await YouTube.slider(query, query_type)
        buttons = slider_markup(_, vidid, user_id, query, query_type, cplay, fplay)
        med = InputMediaPhoto(
            media=thumbnail,
            caption=_["play_10"].format(
                title.title(),
                duration_min,
            ),
        )
        return await CallbackQuery.edit_message_media(
            media=med, reply_markup=InlineKeyboardMarkup(buttons)
        )

@app.on_callback_query(filters.regex("GetUpNext") & ~BANNED_USERS)
@languageCB
async def upnext_suggestions(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    videoid, user_id, channel, fplay = callback_request.split("|")
    
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return

    try:
        await CallbackQuery.answer(_["playcb_2"])
    except:
        pass

    # Try Vortex Suggestions
    try:
        # Get current title to search Vortex
        title, _, _, _, _, _ = await YouTube.details(videoid)
        v_results = await Vortex.search(title)
        if v_results:
            v_id = v_results[0].get("id")
            v_suggestions = await Vortex.get_suggestions(v_id)
            if v_suggestions:
                # Format Vortex suggestions to match upnext_markup expectation
                suggestions = []
                for s in v_suggestions:
                    suggestions.append({
                        "id": f"vortex_{s.get('id')}",
                        "title": s.get("name"),
                    })
                
                buttons = upnext_markup(_, user_id, channel, fplay, suggestions, videoid, 0)
                return await CallbackQuery.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
    except Exception as e:
        print(f"Vortex Suggestion Error: {e}")

    # Fallback to YouTube
    suggestions = await YouTube.get_recommendations(videoid)
    if not suggestions:
        return await CallbackQuery.answer("No suggestions found!", show_alert=True)

    buttons = upnext_markup(_, user_id, channel, fplay, suggestions, videoid, 0)
    
    try:
        await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        print(f"Error editing markup: {e}")

@app.on_callback_query(filters.regex("LoadMore") & ~BANNED_USERS)
@languageCB
async def load_more_cb(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    videoid, user_id, channel, fplay, offset = callback_request.split("|")
    offset = int(offset)

    if CallbackQuery.from_user.id != int(user_id) and int(user_id) != 0:
        try:
            return await CallbackQuery.answer(_["playcb_1"], show_alert=True)
        except:
            return

    try:
        await CallbackQuery.answer(_["playcb_2"])
    except:
        pass

    # Try Vortex Suggestions
    try:
        title, _, _, _, _, _ = await YouTube.details(videoid)
        v_results = await Vortex.search(title)
        if v_results:
            v_id = v_results[0].get("id")
            v_suggestions = await Vortex.get_suggestions(v_id)
            if v_suggestions:
                suggestions = []
                for s in v_suggestions:
                    suggestions.append({
                        "id": f"vortex_{s.get('id')}",
                        "title": s.get("name"),
                    })
                
                buttons = upnext_markup(_, user_id, channel, fplay, suggestions, videoid, offset)
                return await CallbackQuery.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
    except Exception as e:
        print(f"Vortex LoadMore Error: {e}")

    # Fallback to YouTube
    suggestions = await YouTube.get_recommendations(videoid)
    if not suggestions:
        return await CallbackQuery.answer("No more suggestions!", show_alert=True)

    buttons = upnext_markup(_, user_id, channel, fplay, suggestions, videoid, offset)
    
    try:
        await CallbackQuery.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        print(f"Error editing markup in LoadMore: {e}")

@app.on_callback_query(filters.regex("AutoplayToggle") & ~BANNED_USERS)
@languageCB
async def autoplay_toggle_cb(client, CallbackQuery, _):
    if CallbackQuery.from_user.id not in SUDOERS and CallbackQuery.from_user.id != OWNER_ID:
        return await CallbackQuery.answer("🚫 ᴏɴʟʏ sᴜᴅᴏ ᴜsᴇʀs ᴏʀ ᴛʜᴇ ᴏᴡɴᴇʀ ᴄᴀɴ ᴍᴀɴᴀɢᴇ ᴀᴜᴛᴏᴘʟᴀʏ.", show_alert=True)
    callback_data = CallbackQuery.data.strip()
    chat_id = callback_data.split(None, 1)[1]
    
    if chat_id == "suggestion":
        # Handle toggle from suggestions panel
        # Since we don't have chat_id in suggestions callback data easily, 
        # we assuming it's the current chat
        chat_id = CallbackQuery.message.chat.id
    else:
        chat_id = int(chat_id)

    is_on = await is_autoplay(chat_id)
    if is_on:
        await autoplay_off(chat_id)
        await CallbackQuery.answer("Autoplay Disabled", show_alert=True)
    else:
        await autoplay_on(chat_id)
        await CallbackQuery.answer("Autoplay Enabled", show_alert=True)
    
    # Update the markup to reflect the new state if it's the main stream markup
    # Note: For suggestions, we might not need to update immediately or we can re-render
    if "AutoplayToggle suggestion" not in callback_data:
        try:
            # Get videoid from current playing track
            playing = db.get(chat_id)
            videoid = playing[0].get("vidid") if playing else "youtube"
            
            # Determine show_lyrics and lyric_url
            show_lyrics = False
            lyric_url = None
            if playing:
                syn = playing[0].get("synced_lyrics")
                pla = playing[0].get("plain_lyrics")
                if syn or pla:
                    show_lyrics = True
                    lyric_url = playing[0].get("lyric_url")

            from Opus.utils.database import is_on_playlist
            liked = await is_on_playlist(user_id, videoid)
            buttons = stream_markup_autoplay(_, videoid, chat_id, not is_on, liked=liked, show_lyrics=show_lyrics, lyric_url=lyric_url)
            await CallbackQuery.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            pass
