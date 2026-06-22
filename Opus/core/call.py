import os
import time
import config
import asyncio
from typing import Union

from pyrogram import Client
from pyrogram.errors import FloodWait
from strings import get_string
from pytgcalls import PyTgCalls
from datetime import datetime, timedelta
from pyrogram.types import InlineKeyboardMarkup, InputMediaPhoto
from ntgcalls import ConnectionNotFound, TelegramServerError
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    NotInGroupCallError,
)
from pytgcalls.types import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    Update,
)
from pytgcalls.types.stream import StreamAudioEnded

from Opus import YouTube, app
from Opus.misc import db
from Opus.logging import LOGGER
from Opus.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoplay,
    is_autoend,
    is_music_playing,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
    get_thumb_setting,
)
from Opus.utils.exceptions import AssistantErr
from Opus.utils.formatters import check_duration, seconds_to_min, speed_converter
from Opus.utils.inline.play import stream_markup, stream_markup_timer
from Opus.utils.stream.autoclear import auto_clean
from Opus.utils.thumbnails import get_thumb

autoend = {}
counter = {}
db_locks = {}
PLAYED_TRACKS = {}
START_TIMES = {}
loop = asyncio.get_event_loop_policy().get_event_loop()

DEFAULT_AQ = AudioQuality.STUDIO
DEFAULT_VQ = VideoQuality.FHD_1080p
ELSE_AQ = AudioQuality.HIGH

def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    # Use Flags if available ; otherwise omit video_flags
    flags = getattr(MediaStream, "Flags", None)
    
    # If path is a remote URL, add reconnect parameters for FFmpeg to prevent auto-ending/stuttering
    if isinstance(path, str) and path.startswith("http"):
        reconnect_params = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        if ffmpeg_params:
            ffmpeg_params = f"{reconnect_params} {ffmpeg_params}"
        else:
            ffmpeg_params = reconnect_params

    if video:
        if flags is not None:
            return MediaStream(
                path,
                audio_parameters=DEFAULT_AQ,
                video_parameters=DEFAULT_VQ,
                video_flags=(flags.AUTO_DETECT if video else flags.IGNORE),
                ffmpeg_parameters=ffmpeg_params,
            )
        return MediaStream(
            path,
            audio_parameters=DEFAULT_AQ,
            video_parameters=DEFAULT_VQ,
            ffmpeg_parameters=ffmpeg_params,
        )
    else:
        return MediaStream(
            path,
            audio_parameters=ELSE_AQ,
            ffmpeg_parameters=ffmpeg_params,
        )



async def _reboot_log(message: str):
    """Helper to log smart reboot/resume events to logs/reboot.txt"""
    try:
        import os
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("logs/reboot.txt", "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


async def _clear_(chat_id):
    try:
        from Opus.utils.database import clear_persisted_queue
        await clear_persisted_queue(chat_id)
    except:
        pass
    try:
        if chat_id in db:
            del db[chat_id]
        if chat_id in START_TIMES:
            del START_TIMES[chat_id]
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
    except:
        pass

class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            name="OpusXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1, cache_duration=100)

        self.userbot2 = Client(
            name="OpusXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(self.userbot2, cache_duration=100)

        self.userbot3 = Client(
            name="OpusXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(self.userbot3, cache_duration=100)

        self.userbot4 = Client(
            name="OpusXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(self.userbot4, cache_duration=100)

        self.userbot5 = Client(
            name="OpusXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(self.userbot5, cache_duration=100)    

    async def background_persistence(self):
        """Periodically saves all active queues and current timestamps to MongoDB"""
        from Opus.utils.database import persist_queue, clear_persisted_queue
        while not await asyncio.sleep(15): # Save every 15 seconds for high precision
            try:
                for chat_id in list(db.keys()):
                    if db[chat_id]:
                        # Update the played timestamp for the currently playing track
                        if chat_id in START_TIMES:
                            played = int(time.time() - START_TIMES[chat_id])
                            # Only update if valid and not too small
                            if played > 5:
                                db[chat_id][0]["played"] = played
                                
                        await persist_queue(chat_id, db[chat_id])
                    else:
                        await clear_persisted_queue(chat_id)
            except Exception as e:
                LOGGER(__name__).error(f"Persistence Loop Error: {e}")

    async def stop(self):
        """Gracefully saves all active states on shutdown"""
        from Opus.utils.database import persist_queue, clear_persisted_queue
        LOGGER(__name__).info("[bold cyan]● DATABASE[/bold cyan] | Writing active streaming queues to MongoDB...")
        await _reboot_log("--- SYSTEM SHUTDOWN INITIATED ---")

        try:
            for chat_id in list(db.keys()):
                if db[chat_id]:
                    if chat_id in START_TIMES:
                        db[chat_id][0]["played"] = int(time.time() - START_TIMES[chat_id])
                    await persist_queue(chat_id, db[chat_id])
        except Exception as e:
            LOGGER(__name__).error(f"Shutdown Save Error: {e}")

    async def startup_resume(self):
        """Restores all playing tracks and queues with precise timestamps from MongoDB on startup"""
        from Opus.utils.database import get_persisted_queues, clear_persisted_queue
        LOGGER(__name__).info("[bold cyan]● RESUME[/bold cyan] | Initiating smart playback resume sequence...")
        await _reboot_log("--- SMART RESUME SEQUENCE STARTED ---")

        
        try:
            persisted = await get_persisted_queues()
            if not persisted:
                LOGGER(__name__).info("[bold cyan]● RESUME[/bold cyan] | No persistence states discovered.")
                await _reboot_log("No persisted queues found in database.")
                return


            for chat_id, queue in persisted.items():
                try:
                    if not queue:
                        continue
                    
                    db[chat_id] = queue
                    first_track = queue[0]
                    file_path = first_track.get("file")
                    is_video = (first_track.get("streamtype") == "video")
                    played_offset = first_track.get("played", 0)
                    duration_seconds = first_track.get("seconds", 0)
                    
                    # If track was already finished (played >= 90% of duration), skip to next
                    if duration_seconds > 0 and played_offset >= (duration_seconds * 0.9):
                        await _reboot_log(f"Track in {chat_id} was already finished ({played_offset}s/{duration_seconds}s), skipping...")
                        if len(queue) > 1:
                            db[chat_id].pop(0)
                            first_track = db[chat_id][0]
                            file_path = first_track.get("file")
                            is_video = (first_track.get("streamtype") == "video")
                            played_offset = 0  # Start next track from beginning
                            duration_seconds = first_track.get("seconds", 0)
                            first_track["played"] = 0
                        else:
                            await _reboot_log(f"No more tracks in queue for {chat_id}, clearing.")
                            await clear_persisted_queue(chat_id)
                            if chat_id in db:
                                del db[chat_id]
                            continue
                    
                    if file_path and (file_path.startswith("http") or os.path.exists(file_path)):
                        await add_active_chat(chat_id)
                        if is_video:
                            await add_active_video_chat(chat_id)
                        
                        assistant = await group_assistant(self, chat_id)
                        
                        # Refresh URL if it's a YouTube stream (URLs expire)
                        vidid = first_track.get("vidid")
                        if vidid and file_path.startswith("http") and not str(vidid).startswith("vortex_"):
                            from Opus import YouTube
                            n, new_path = await YouTube.video(vidid, is_video=is_video)
                            if n in (1, 2):
                                file_path = new_path
                                db[chat_id][0]["file"] = new_path
                        
                        # Apply seek parameters if the track was partially played
                        ffmpeg_params = None
                        if played_offset > 10 and (duration_seconds == 0 or played_offset < duration_seconds - 5):
                            ffmpeg_params = f"-ss {played_offset}"
                            LOGGER(__name__).info(f"Resuming {chat_id} from {played_offset}s")
                        
                        stream = dynamic_media_stream(file_path, video=is_video, ffmpeg_params=ffmpeg_params)
                        
                        resumed = False
                        try:
                            await assistant.join_group_call(chat_id, stream)
                            START_TIMES[chat_id] = time.time() - played_offset
                            LOGGER(__name__).info(f"Resumed playback in {chat_id}")
                            await _reboot_log(f"SUCCESS: Resumed '{first_track.get('title')[:30]}' in {chat_id} at {played_offset}s")
                            resumed = True

                        except AlreadyJoinedError:
                            await assistant.change_stream(chat_id, stream)
                            START_TIMES[chat_id] = time.time() - played_offset
                            resumed = True
                        except BaseException as e:
                            # Direct stream failed — try downloading
                            LOGGER(__name__).info(f"Stream failed for {chat_id}, trying download fallback...")
                            if vidid:
                                try:
                                    from Opus import YouTube
                                    dl_path, _ = await YouTube.download(
                                        vidid, None, videoid=True, video=is_video
                                    )
                                    if dl_path and os.path.exists(dl_path):
                                        from config import autoclean
                                        if dl_path not in autoclean:
                                            autoclean.append(dl_path)
                                        file_path = dl_path
                                        db[chat_id][0]["file"] = dl_path
                                        stream = dynamic_media_stream(dl_path, video=is_video, ffmpeg_params=ffmpeg_params)
                                        try:
                                            await assistant.join_group_call(chat_id, stream)
                                            START_TIMES[chat_id] = time.time() - played_offset
                                            LOGGER(__name__).info(f"Resumed {chat_id} via download fallback")
                                            resumed = True
                                        except AlreadyJoinedError:
                                            await assistant.change_stream(chat_id, stream)
                                            START_TIMES[chat_id] = time.time() - played_offset
                                            resumed = True
                                        except BaseException as e2:
                                            LOGGER(__name__).error(f"Download fallback also failed for {chat_id}: {e2}")
                                            await clear_persisted_queue(chat_id)
                                    else:
                                        LOGGER(__name__).error(f"Download returned no file for {chat_id}")
                                        await clear_persisted_queue(chat_id)
                                except BaseException as e3:
                                    LOGGER(__name__).error(f"Download fallback error for {chat_id}: {e3}")
                                    await clear_persisted_queue(chat_id)
                            else:
                                LOGGER(__name__).error(f"No vidid to download for {chat_id}")
                                await clear_persisted_queue(chat_id)
                        
                        # Send resume notification if playback was successfully restored
                        if resumed:
                            await music_on(chat_id)
                            await self._send_resume_notification(chat_id, first_track, played_offset)
                            
                except BaseException as e:
                    LOGGER(__name__).error(f"Error resuming chat {chat_id}: {e}")
                    await _reboot_log(f"FAILED: Chat {chat_id} resume error: {e}")
        except BaseException as e:
            LOGGER(__name__).error(f"Startup Resume Error: {e}")
            await _reboot_log(f"CRITICAL: Startup Resume Engine Error: {e}")


    async def _send_resume_notification(self, chat_id, track, played_offset):
        """Send or edit a 'Resumed' now-playing message after Smart Resume"""
        try:
            original_chat_id = track.get("chat_id", chat_id)
            title = track.get("title", "Unknown")
            vidid = track.get("vidid", "")
            dur = track.get("dur", "00:00")
            user = track.get("by", "Smart Resume")
            performer = track.get("performer", "Artist")
            thumbnail = track.get("thumb")

            # Build progress string
            played_min = seconds_to_min(played_offset) if played_offset > 0 else "00:00"
            
            resume_caption = (
                f"<blockquote><b>﹝  sᴍᴀʀᴛ ʀᴇsᴜᴍᴇ   ﹞</b></blockquote>\n"
                f"<blockquote>• <b>{title[:23]}</b>\n"
                f"• <b>{user}</b></blockquote>\n"
                f"<blockquote><i><b>ᴄʀᴀꜰᴛᴇᴅ ᴛᴏ ʙᴇ ʜᴇᴀʀᴅ. ʙᴜɪʟᴛ ᴛᴏ ʙᴇ ꜰᴇʟᴛ.</b></i></blockquote>"
            )

            from Opus.utils.database import is_on_playlist
            liked = await is_on_playlist(track.get("user_id", 0), vidid)
            button = stream_markup_timer(
                get_string("en"), vidid, chat_id, played_min, dur, liked=liked
            )

            # Try to edit old "mystic" message if it exists in db
            old_mystic = track.get("mystic")
            thumb_on = await get_thumb_setting(original_chat_id)

            # Generate thumbnail
            img = None
            if thumb_on and vidid:
                try:
                    if thumbnail and thumbnail.startswith("http"):
                        img = await get_thumb(vidid, force_url=thumbnail, force_title=title, chat_id=original_chat_id)
                    else:
                        img = await get_thumb(vidid, chat_id=original_chat_id)
                except:
                    pass

            # Try editing old message first
            edited = False
            if old_mystic:
                try:
                    msg_id = old_mystic if isinstance(old_mystic, int) else getattr(old_mystic, "id", None)
                    if msg_id:
                        if img and thumb_on:
                            await app.edit_message_media(
                                chat_id=original_chat_id,
                                message_id=msg_id,
                                media=InputMediaPhoto(img, caption=resume_caption),
                                reply_markup=InlineKeyboardMarkup(button),
                            )
                        else:
                            await app.edit_message_text(
                                chat_id=original_chat_id,
                                message_id=msg_id,
                                text=resume_caption,
                                reply_markup=InlineKeyboardMarkup(button),
                                disable_web_page_preview=True,
                            )
                        edited = True
                        # Fetch the fresh Message object so markup_timer() can update it
                        try:
                            fresh_msg = await app.get_messages(original_chat_id, msg_id)
                            if chat_id in db and db[chat_id]:
                                db[chat_id][0]["mystic"] = fresh_msg
                                db[chat_id][0]["markup"] = "stream"
                        except:
                            pass
                except:
                    # Old message couldn't be edited — delete it
                    try:
                        msg_id = old_mystic if isinstance(old_mystic, int) else getattr(old_mystic, "id", None)
                        if msg_id:
                            await app.delete_messages(original_chat_id, msg_id)
                    except:
                        pass

            # Send fresh message if edit failed
            if not edited:
                if img and thumb_on:
                    run = await app.send_photo(
                        original_chat_id,
                        photo=img,
                        caption=resume_caption,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_message(
                        original_chat_id,
                        text=resume_caption,
                        reply_markup=InlineKeyboardMarkup(button),
                        disable_web_page_preview=True,
                    )
                # Update db with new message reference
                if chat_id in db and db[chat_id]:
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

        except Exception as e:
            LOGGER(__name__).error(f"Resume notification error for {chat_id}: {e}")


    async def pause_stream(self, chat_id: int, is_auto: bool = False):
        assistant = await group_assistant(self, chat_id)
        try:
            await assistant.pause_stream(chat_id)
            if chat_id in START_TIMES:
                if chat_id in db and db[chat_id]:
                    db[chat_id][0]["played"] = int(time.time() - START_TIMES[chat_id])
                del START_TIMES[chat_id]
        except Exception as e:
            LOGGER(__name__).error(f"Error while pausing stream for {chat_id}: {e}")
            
        if is_auto and await is_autoend(chat_id):
            autoend[chat_id] = datetime.now() + timedelta(minutes=3)
        
        # Backup Download Logic
        if chat_id in db:
            check = db.get(chat_id)
            if check:
                file_path = check[0].get("file")
                if file_path and file_path.startswith("http"):
                    # Start background download after a short delay (e.g. 10 seconds of pause)
                    async def delayed_backup(c_id, path, vid, title, dur):
                        await asyncio.sleep(10) # Wait 10 seconds
                        # Check if still paused and still same track
                        if c_id in db and db[c_id][0].get("file") == path and not await is_music_playing(c_id):
                            try:
                                from Opus.utils.downloader import download_audio
                                local_path = await download_audio(path, title=title, duration_sec=dur)
                                if local_path and os.path.exists(local_path):
                                    db[c_id][0]["file"] = local_path
                                    # Add to autoclean
                                    from config import autoclean
                                    if local_path not in autoclean:
                                        autoclean.append(local_path)
                            except Exception as e:
                                LOGGER(__name__).error(f"Backup Download Failed for {c_id}: {e}")

                    asyncio.create_task(delayed_backup(
                        chat_id, 
                        file_path, 
                        check[0].get("vidid"), 
                        check[0].get("title"), 
                        check[0].get("seconds")
                    ))

    async def mute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.mute_stream(chat_id)

    async def unmute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute_stream(chat_id)

    async def get_participant(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        return await assistant.get_participants(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await assistant.resume_stream(chat_id)
            if chat_id in db and db[chat_id]:
                played = db[chat_id][0].get("played", 0)
                START_TIMES[chat_id] = time.time() - played
        except Exception as e:
            LOGGER(__name__).error(f"Error while resuming stream for chat {chat_id}: {e}")
            try:
                if chat_id in db:
                    check = db.get(chat_id)
                    if check:
                        file_path = check[0].get("file")
                        streamtype = check[0].get("streamtype")
                        played = check[0].get("played") or 0
                        duration = check[0].get("dur")
                        if file_path:
                            # If the resume failed and it was a URL, try to download it now or use existing local path
                            if file_path.startswith("http"):
                                try:
                                    from Opus.utils.downloader import download_audio
                                    local_path = await download_audio(file_path, title=check[0].get("title"), duration_sec=check[0].get("seconds"))
                                    if local_path and os.path.exists(local_path):
                                        file_path = local_path
                                        db[chat_id][0]["file"] = local_path
                                except:
                                    pass

                            # Use offset to resume accurately if possible
                            ffmpeg_params = (
                                f"-ss {played} -to {duration}"
                                if played > 0 and duration
                                else ""
                            )
                            stream = dynamic_media_stream(
                                file_path,
                                video=(str(streamtype) == "video"),
                                ffmpeg_params=ffmpeg_params,
                            )
                            await assistant.change_stream(chat_id, stream)
            except Exception as ex:
                LOGGER(__name__).error(f"Fallback resume failed for chat {chat_id}: {ex}")

        if chat_id in autoend:
            autoend.pop(chat_id, None)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            try:
                await assistant.leave_group_call(chat_id)
            except (NoActiveGroupCall, NotInGroupCallError):
                pass
        except:
            pass

    async def stop_stream_force(self, chat_id: int):
        for client in [self.one, self.two, self.three, self.four, self.five]:
            try:
                await client.leave_group_call(chat_id)
            except (NoActiveGroupCall, NotInGroupCallError):
                pass
            except:
                pass
        await _clear_(chat_id)

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == "0.5":
                    vs = 2.0
                if str(speed) == "0.75":
                    vs = 1.35
                if str(speed) == "1.5":
                    vs = 0.68
                if str(speed) == "2.0":
                    vs = 0.5
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        "ffmpeg "
                        "-i "
                        f"{file_path} "
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path

        dur = await loop.run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)

        stream = dynamic_media_stream(
            out,
            video=(playing[0]["streamtype"] == "video"),
            ffmpeg_params=f"-ss {played} -to {duration}",
        )

        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.change_stream(chat_id, stream)
            START_TIMES[chat_id] = time.time() - con_seconds
        else:
            raise AssistantErr("Umm")

        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            from Opus.utils.database import clear_persisted_queue
            await clear_persisted_queue(chat_id)
        except:
            pass
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except:
            pass
        if chat_id in START_TIMES:
            del START_TIMES[chat_id]
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_group_call(chat_id)
        except (NoActiveGroupCall, NotInGroupCallError):
            pass
        except:
            pass

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(link, video=bool(video))
        try:
            await assistant.change_stream(chat_id, stream)
            START_TIMES[chat_id] = time.time()
        except:
            try:
                await app.send_message(chat_id, text="Failed to skip stream due to an error.")
            except:
                pass

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(
            file_path,
            video=(mode == "video"),
            ffmpeg_params=f"-ss {to_seek} -to {duration}",
        )
        try:
            await assistant.change_stream(chat_id, stream)
            START_TIMES[chat_id] = time.time() - to_seek
        except:
            pass

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        try:
            await assistant.join_group_call(config.LOGGER_ID, dynamic_media_stream(link, video=True))
            await asyncio.sleep(2)
            try:
                await assistant.leave_group_call(config.LOGGER_ID)
            except (NoActiveGroupCall, NotInGroupCallError):
                pass
        except:
            pass


    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        strings = get_string(language)

        stream = dynamic_media_stream(link, video=bool(video))

        try:
            await assistant.join_group_call(chat_id, stream)
        except NoActiveGroupCall:
            raise AssistantErr(strings["call_8"])
        except AlreadyJoinedError:
            raise AssistantErr(strings["call_9"])
        except TelegramServerError:
            raise AssistantErr(strings["call_10"])
        except ConnectionNotFound:
            raise AssistantErr(strings["call_10"])
        except Exception as e:
            if "phone.CreateGroupCall" in str(e):
                raise AssistantErr(strings["call_8"])
            raise AssistantErr("Failed to join voice chat due to an unknown error.")

        await add_active_chat(chat_id)
        await music_on(chat_id)
        if chat_id in db and db[chat_id]:
            db[chat_id][0]["played"] = 0
        START_TIMES[chat_id] = time.time()
        if video:
            await add_active_video_chat(chat_id)

        if await is_autoend(chat_id):
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=3)

    async def attempt_stream(self, client, chat_id, stream, retries=1):
        for _ in range(retries):
            try:
                await client.change_stream(chat_id, stream)
                # Reset start time for accurate persistence
                played = 0
                if chat_id in db and db[chat_id]:
                    played = db[chat_id][0].get("played", 0)
                START_TIMES[chat_id] = time.time() - played
                return True
            except:
                await asyncio.sleep(0.5)
        return False

    async def check_autoend(self, chat_id):
        if not await is_autoend(chat_id):
            return
        
        # If manually paused, don't auto-end (allow "resume anytime")
        if not await is_music_playing(chat_id):
            if chat_id in autoend:
                autoend.pop(chat_id, None)
            return

        try:
            users = len(await (await group_assistant(self, chat_id)).get_participants(chat_id))
        except:
            return
        if users <= 1:
            if chat_id not in autoend:
                autoend[chat_id] = datetime.now() + timedelta(minutes=3)
            elif datetime.now() > autoend[chat_id]:
                await self.stop_stream(chat_id)
                autoend.pop(chat_id, None)
                try:
                    await app.send_message(
                        chat_id,
                        "» ʙᴏᴛ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ʟᴇғᴛ ᴠɪᴅᴇᴏᴄʜᴀᴛ ʙᴇᴄᴀᴜsᴇ ɴᴏ ᴏɴᴇ ᴡᴀs ʟɪsᴛᴇɴɪɴɢ ᴏɴ ᴠɪᴅᴇᴏᴄʜᴀᴛ.",
                    )
                except:
                    pass
        else:
            autoend.pop(chat_id, None)

    async def change_stream(self, client, chat_id):
        if chat_id not in db_locks:
            db_locks[chat_id] = asyncio.Lock()

        async with db_locks[chat_id]:
            if chat_id in START_TIMES:
                del START_TIMES[chat_id]
            check = db.get(chat_id)
            popped = None
            loop_count = await get_loop(chat_id)

            if not check or len(check) == 0:
                if await is_autoplay(chat_id):
                    # ...
                    # We don't have 'popped' yet if we return here, 
                    # but usually change_stream is called when a song is ALREADY finished.
                    # The last song is NOT in check anymore if it was popped in a previous call.
                    # Wait, let's look at the flow.
                    pass
                await _clear_(chat_id)
                try:
                    await client.leave_group_call(chat_id)
                except (NoActiveGroupCall, NotInGroupCallError):
                    pass
                return
            if loop_count == 0:
                popped = check.pop(0)
            else:
                loop_count = loop_count - 1
                await set_loop(chat_id, loop_count)
            if popped:
                await auto_clean(popped)
            if not check or len(check) == 0:
                if popped:
                    vidid = popped.get("vidid")
                    if vidid:
                        try:
                            if vidid.startswith("vortex_"):
                                # --- VORTEX AUTOPLAY LOGIC ---
                                v_id = vidid.replace("vortex_", "")
                                from Opus import Vortex
                                suggestions = await Vortex.get_suggestions(v_id)
                                if suggestions:
                                    language = await get_lang(chat_id)
                                    _trans = get_string(language)
                                    if await is_autoplay(chat_id):
                                        from Opus.utils.stream.stream import stream
                                        if chat_id not in PLAYED_TRACKS:
                                            PLAYED_TRACKS[chat_id] = []
                                        if vidid not in PLAYED_TRACKS[chat_id]:
                                            PLAYED_TRACKS[chat_id].append(vidid)
                                        top = None
                                        for s in suggestions:
                                            if not s.get("id"):
                                                continue
                                            s_id = f"vortex_{s.get('id')}"
                                            if s_id not in PLAYED_TRACKS[chat_id]:
                                                # Skip long tracks in autoplay
                                                try:
                                                    duration_vortex = int(s.get("duration") or 0)
                                                except:
                                                    duration_vortex = 0
                                                
                                                if duration_vortex > config.DURATION_LIMIT:
                                                    continue
                                                top = s
                                                break
                                        if not top:
                                            top = suggestions[0]
                                        t_id = f"vortex_{top.get('id')}"
                                        if t_id not in PLAYED_TRACKS[chat_id]:
                                            PLAYED_TRACKS[chat_id].append(t_id)
                                        if len(PLAYED_TRACKS[chat_id]) > 50:
                                            PLAYED_TRACKS[chat_id] = PLAYED_TRACKS[chat_id][-50:]
                                        
                                        title = top.get("name", "Unknown")
                                        images = top.get("image", [])
                                        thumb = images[-1].get("url") if images else config.YOUTUBE_IMG_URL
                                        duration_sec = top.get("duration") or 0
                                        from Opus.utils.formatters import seconds_to_min
                                        duration_min = seconds_to_min(duration_sec)
                                        link = top.get("downloadUrl", [])
                                        link = link[-1].get("url") if link else None
                                        
                                        track_data = {
                                            "title": title,
                                            "link": link,
                                            "vidid": t_id,
                                            "duration_min": duration_min,
                                            "thumb": thumb,
                                            "path": link,
                                        }
                                        user_id = popped.get("by_id") or (config.OWNER_ID[0] if isinstance(config.OWNER_ID, list) else config.OWNER_ID)
                                        user_name = popped.get("by") or "Autoplay"
                                        await stream(
                                            _trans,
                                            None,
                                            user_id,
                                            track_data,
                                            chat_id,
                                            user_name,
                                            chat_id,
                                            video=(popped.get("streamtype") == "video"),
                                            streamtype="vortex",
                                            forceplay=True,
                                        )
                                        return
                                    else:
                                        from Opus.utils.inline.play import upnext_markup
                                        buttons = upnext_markup(_trans, 0, None, None, suggestions, vidid, 0)
                                        await app.send_message(
                                            chat_id=chat_id,
                                            text=_trans["play_22"] if "play_22" in _trans else "<blockquote><b>ǫᴜᴇᴜᴇ ᴇɴᴅᴇᴅ. ʜᴇʀᴇ ᴀʀᴇ sᴏᴍᴇ sᴜɢɢᴇsᴛɪᴏɴs...</b></blockquote>",
                                            reply_markup=InlineKeyboardMarkup(buttons),
                                        )
                            else:
                                # --- ORIGINAL YOUTUBE AUTOPLAY LOGIC (UNTOUCHED) ---
                                suggestions = await YouTube.get_recommendations(vidid)
                                if suggestions:
                                    language = await get_lang(chat_id)
                                    _trans = get_string(language)
                                    
                                    if await is_autoplay(chat_id):
                                        from Opus.utils.stream.stream import stream
                                        if chat_id not in PLAYED_TRACKS:
                                            PLAYED_TRACKS[chat_id] = []
                                        if vidid not in PLAYED_TRACKS[chat_id]:
                                            PLAYED_TRACKS[chat_id].append(vidid)
                                        top = None
                                        for s in suggestions:
                                            if not s.get("id"):
                                                continue
                                            if s.get("id") not in PLAYED_TRACKS[chat_id]:
                                                # Skip long tracks in autoplay
                                                from Opus.utils.formatters import time_to_seconds
                                                dur = s.get("duration")
                                                if time_to_seconds(dur) > config.DURATION_LIMIT:
                                                    continue
                                                top = s
                                                break
                                        if not top:
                                            top = suggestions[0]
                                        
                                        if top.get("id") not in PLAYED_TRACKS[chat_id]:
                                            PLAYED_TRACKS[chat_id].append(top.get("id"))
                                        if len(PLAYED_TRACKS[chat_id]) > 50:
                                            PLAYED_TRACKS[chat_id] = PLAYED_TRACKS[chat_id][-50:]
                                        
                                        thumb = config.YOUTUBE_IMG_URL
                                        t = top.get("thumbnails") or top.get("thumb")
                                        if isinstance(t, list) and len(t) > 0:
                                            thumb = t[0].get("url")
                                        elif isinstance(t, str) and t.startswith("http"):
                                            thumb = t
                                        duration = top.get("duration")
                                        if not duration or not isinstance(duration, str) or ":" not in duration:
                                            duration = "05:00"
                                        
                                        track_data = {
                                            "title": top.get("title"),
                                            "link": top.get("link"),
                                            "vidid": top.get("id"),
                                            "duration_min": duration,
                                            "thumb": thumb,
                                        }
                                        user_id = popped.get("by_id") or (config.OWNER_ID[0] if isinstance(config.OWNER_ID, list) else config.OWNER_ID)
                                        user_name = popped.get("by") or "Autoplay"
                                        
                                        await stream(
                                            _trans,
                                            None,
                                            user_id,
                                            track_data,
                                            chat_id,
                                            user_name,
                                            chat_id,
                                            video=(popped.get("streamtype") == "video"),
                                            streamtype="youtube",
                                            forceplay=True,
                                        )
                                        return
                                    else:
                                        from Opus.utils.inline.play import upnext_markup
                                        buttons = upnext_markup(_trans, 0, None, None, suggestions, vidid, 0)
                                        await app.send_message(
                                            chat_id=chat_id,
                                            text=_trans["play_22"] if "play_22" in _trans else "<blockquote><b>ǫᴜᴇᴜᴇ ᴇɴᴅᴇᴅ. ʜᴇʀᴇ ᴀʀᴇ sᴏᴍᴇ sᴜɢɢᴇsᴛɪᴏɴs ʙᴀsᴇᴅ ᴏɴ ʏᴏᴜʀ ᴠɪʙᴇ !!</b></blockquote>",
                                            reply_markup=InlineKeyboardMarkup(buttons),
                                        )
                        except Exception as e:
                            LOGGER(__name__).error(f"Autoplay/Suggestions Error: {e}")
                await _clear_(chat_id)
                try:
                    await client.leave_group_call(chat_id)
                except (NoActiveGroupCall, NotInGroupCallError):
                    pass
                return
        if chat_id not in db or not db.get(chat_id):
            return
        queued = check[0].get("file")
        if not queued:
            await _clear_(chat_id)
            try:
                await client.leave_group_call(chat_id)
            except (NoActiveGroupCall, NotInGroupCallError):
                pass
            return
        language = await get_lang(chat_id)
        strings = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        user_id = check[0].get("user_id", 0)
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        thumbnail = check[0].get("thumb")
        thumb_mode = await get_thumb_setting(original_chat_id)
        db[chat_id][0]["played"] = 0
        if exis := (check[0]).get("old_dur"):
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0
        is_video = (str(streamtype) == "video")
        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                try:
                    await app.send_message(original_chat_id, text=strings["call_6"])
                except:
                    pass
                await _clear_(chat_id)
                return
            stream = dynamic_media_stream(link, video=is_video)
            if not await self.attempt_stream(client, chat_id, stream):
                try:
                    await app.send_message(original_chat_id, text=strings["call_6"])
                except:
                    pass
                await _clear_(chat_id)
                return
            if thumbnail and thumbnail.startswith("http"):
                img = await get_thumb(videoid, force_url=thumbnail, force_title=title, chat_id=original_chat_id)
            else:
                img = await get_thumb(videoid, chat_id=original_chat_id)
            from Opus.utils.database import is_on_playlist
            liked = await is_on_playlist(user_id, videoid)
            button = stream_markup(strings, videoid, chat_id, liked=liked)
            caption_text = strings["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user, check[0].get("performer", "YouTube Live")
            )
            if thumb_mode:
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    chat_id=original_chat_id,
                    text=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                    disable_web_page_preview=True,
                )
            if chat_id in db and db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
        elif "vid_" in queued:
            mystic = await app.send_message(original_chat_id, strings["call_7"])
            try:
                if videoid.startswith("vortex_"):
                    v_id = videoid.replace("vortex_", "")
                    from Opus import Vortex
                    from Opus.utils.downloader import download_url
                    
                    details = await Vortex.details(v_id)
                    if not details:
                        raise Exception("Failed to fetch Vortex details")
                    
                    download_url_path = details.get("path")
                    file_path = await download_url(download_url_path)
                    direct = False
                    
                    from config import autoclean
                    autoclean.append(file_path)
                else:
                    # Resolve via multi-source resolver with retry
                    import aiofiles as _aiofiles
                    import httpx as _httpx
                    file_path = None
                    direct = False
                    for _attempt in range(1, 3):
                        n, link_direct = await YouTube.video(videoid, is_video=is_video)
                        if n == 2:
                            file_path = link_direct
                            direct = False
                            from config import autoclean
                            if file_path not in autoclean:
                                autoclean.append(file_path)
                            break
                        elif n == 1:
                            # Download locally to prevent auto-end
                            ext = "mp4" if is_video else "mp3"
                            local_path = f"downloads/{videoid}.{ext}"
                            os.makedirs("downloads", exist_ok=True)
                            if os.path.exists(local_path) and os.path.getsize(local_path) > 10240:
                                file_path = local_path
                                direct = False
                            else:
                                try:
                                    async with _httpx.AsyncClient(timeout=60, follow_redirects=True) as dl_client:
                                        async with dl_client.stream("GET", link_direct, timeout=60) as resp:
                                            if resp.status_code == 200:
                                                async with _aiofiles.open(local_path, "wb") as f:
                                                    async for chunk in resp.aiter_bytes(8 * 1024 * 1024):
                                                        if chunk:
                                                            await f.write(chunk)
                                    if os.path.exists(local_path) and os.path.getsize(local_path) > 10240:
                                        file_path = local_path
                                        direct = False
                                    else:
                                        file_path = link_direct
                                        direct = True
                                except Exception:
                                    file_path = link_direct
                                    direct = True
                            if not direct:
                                from config import autoclean
                                if file_path not in autoclean:
                                    autoclean.append(file_path)
                            break
                        else:
                            if _attempt < 2:
                                await asyncio.sleep(2)
                                continue
                            # Final fallback — download via yt-dlp
                            file_path, direct = await YouTube.download(
                                videoid, mystic, videoid=True, video=is_video
                            )
                
                if not file_path:
                    raise Exception("No file path obtained")
                # Only check os.path.exists for local files, not URLs
                if not file_path.startswith("http") and not os.path.exists(file_path):
                    raise Exception("Downloaded file not found on disk")
            except Exception as e:
                LOGGER(__name__).error(f"Queue Download Error: {e}")
                await mystic.edit_text(strings["call_6"], disable_web_page_preview=True)
                await _clear_(chat_id)
                return
            stream = dynamic_media_stream(file_path, video=is_video)
            if not await self.attempt_stream(client, chat_id, stream):
                # Direct stream failed — fall back to download
                if file_path.startswith("http"):
                    LOGGER(__name__).info(f"Direct stream failed for {videoid}, downloading...")
                    try:
                        file_path, direct = await YouTube.download(
                            videoid, mystic, videoid=True, video=is_video
                        )
                        if file_path and os.path.exists(file_path):
                            from config import autoclean
                            if file_path not in autoclean:
                                autoclean.append(file_path)
                            stream = dynamic_media_stream(file_path, video=is_video)
                            if not await self.attempt_stream(client, chat_id, stream):
                                raise Exception("Fallback stream also failed")
                            # Update db with local path
                            if chat_id in db and db[chat_id]:
                                db[chat_id][0]["file"] = file_path
                        else:
                            raise Exception("Download returned no file")
                    except Exception as e2:
                        LOGGER(__name__).error(f"Fallback download also failed: {e2}")
                        try:
                            await app.send_message(original_chat_id, text=strings["call_6"])
                        except:
                            pass
                        await _clear_(chat_id)
                        return
                else:
                    try:
                        await app.send_message(original_chat_id, text=strings["call_6"])
                    except:
                        pass
                    await _clear_(chat_id)
                    return
            if thumbnail and thumbnail.startswith("http"):
                img = await get_thumb(videoid, force_url=thumbnail, force_title=title, chat_id=original_chat_id)
            else:
                img = await get_thumb(videoid, chat_id=original_chat_id)
            from Opus.utils.database import is_on_playlist
            liked = await is_on_playlist(user_id, videoid)
            button = stream_markup(strings, videoid, chat_id, liked=liked, show_lyrics=False)
            await mystic.delete()
            caption_text = strings["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                check[0]["dur"],
                user, check[0].get("performer", "Artist")
            )
            if thumb_mode:
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                )
            else:
                run = await app.send_message(
                    chat_id=original_chat_id,
                    text=caption_text,
                    reply_markup=InlineKeyboardMarkup(button),
                    disable_web_page_preview=True,
                )
            if chat_id in db and db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        elif "index_" in queued:
            stream = dynamic_media_stream(videoid, video=is_video)
            if not await self.attempt_stream(client, chat_id, stream):
                try:
                    await app.send_message(original_chat_id, text=strings["call_6"])
                except:
                    pass
                await _clear_(chat_id)
                return
            button = stream_markup(strings, "index_url", chat_id, show_lyrics=False)
            caption_text = strings["stream_2"].format(user)
            try:
                if thumb_mode:
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.STREAM_IMG_URL,
                        caption=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                else:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=caption_text,
                        reply_markup=InlineKeyboardMarkup(button),
                        disable_web_page_preview=True,
                    )
            except FloodWait as e:
                await asyncio.sleep(e.value)
            if chat_id in db and db.get(chat_id):
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
        else:
            stream = dynamic_media_stream(queued, video=is_video)
            if not await self.attempt_stream(client, chat_id, stream):
                try:
                    await app.send_message(original_chat_id, text=strings["call_6"])
                except:
                    pass
                await _clear_(chat_id)
                return
            if videoid == "telegram":
                button = stream_markup(strings, "telegram", chat_id)
                caption_text = strings["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], check[0]["dur"], user, "Telegram"
                )
                try:
                    if thumb_mode:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL,
                            caption=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    else:
                        run = await app.send_message(
                            chat_id=original_chat_id,
                            text=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                            disable_web_page_preview=True,
                        )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                if chat_id in db and db.get(chat_id):
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
            elif videoid == "soundcloud":
                button = stream_markup(strings, "soundcloud", chat_id)
                caption_text = strings["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], check[0]["dur"], user, "SoundCloud"
                )
                try:
                    if thumb_mode:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=config.SOUNCLOUD_IMG_URL,
                            caption=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    else:
                        run = await app.send_message(
                            chat_id=original_chat_id,
                            text=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                            disable_web_page_preview=True,
                        )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                if chat_id in db and db.get(chat_id):
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
            else:
                if thumbnail and thumbnail.startswith("http"):
                    img = await get_thumb(videoid, force_url=thumbnail, force_title=title, chat_id=original_chat_id)
                else:
                    img = await get_thumb(videoid, chat_id=original_chat_id)
                from Opus.utils.database import is_on_playlist
                liked = await is_on_playlist(user_id, videoid)
                button = stream_markup(strings, videoid, chat_id, liked=liked)
                caption_text = strings["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                    check[0].get("performer", "Artist"),
                )
                try:
                    if thumb_mode:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    else:
                        run = await app.send_message(
                            chat_id=original_chat_id,
                            text=caption_text,
                            reply_markup=InlineKeyboardMarkup(button),
                            disable_web_page_preview=True,
                        )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                if chat_id in db and db.get(chat_id):
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    
    async def ping(self):
        pings = []
        if config.STRING1:
            pings.append(await self.one.ping)
        if config.STRING2:
            pings.append(await self.two.ping)
        if config.STRING3:
            pings.append(await self.three.ping)
        if config.STRING4:
            pings.append(await self.four.ping)
        if config.STRING5:
            pings.append(await self.five.ping)
        return str(round(sum(pings) / len(pings), 3))

    async def start(self):
        LOGGER(__name__).info("[bold cyan]● DRIVERS[/bold cyan] | Booting PyTgCalls audio/video drivers...")
        
        # Start persistence background task
        asyncio.create_task(self.background_persistence())
        
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()


    async def decorators(self):
        @self.one.on_kicked()
        @self.two.on_kicked()
        @self.four.on_kicked()
        @self.five.on_kicked()
        @self.one.on_closed_voice_chat()
        @self.two.on_closed_voice_chat()
        @self.three.on_closed_voice_chat()
        @self.four.on_closed_voice_chat()
        @self.five.on_closed_voice_chat()
        @self.one.on_left()
        @self.two.on_left()
        @self.three.on_left()
        @self.four.on_left()
        @self.five.on_left()
        async def stream_services_handler(_, chat_id: int):
            await self.stop_stream(chat_id)

        @self.one.on_stream_end()
        @self.two.on_stream_end()
        @self.three.on_stream_end()
        @self.four.on_stream_end()
        @self.five.on_stream_end()
        async def stream_end_handler(client, update: Update):
            if not isinstance(update, StreamAudioEnded):
                return
            chat_id = update.chat_id
            try:
                await self.change_stream(client, chat_id)
            except Exception:
                import traceback
                traceback.print_exc()
                
            if not db.get(chat_id):
                await _clear_(chat_id)
                try:
                    await client.leave_group_call(chat_id)
                except (NoActiveGroupCall, NotInGroupCallError):
                    pass


Signal = Call()