import asyncio
from typing import Union

from Opus.misc import db
from Opus.utils.formatters import check_duration, seconds_to_min
from config import autoclean, time_to_seconds


async def put_queue(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    user_id,
    stream,
    forceplay: Union[bool, str] = None,
    thumbnail: str = None,
    performer: str = None,
):
    title = title.title()
    try:
        duration_in_seconds = time_to_seconds(duration) - 3
    except:
        duration_in_seconds = 0
    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "user_id": user_id,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": duration_in_seconds,
        "played": 0,
        "thumb": thumbnail,
        "performer": performer or "Aurex Music",
    }
    if forceplay:
        check = db.get(chat_id)
        if check:
            check.insert(0, put)
        else:
            db[chat_id] = []
            db[chat_id].append(put)
        if user_id:
            from Opus.utils.database import record_play
            asyncio.create_task(record_play(user_id, vidid, title, duration, user_name=user))
    else:
        db[chat_id].append(put)
        if len(db[chat_id]) == 1 and user_id:
            from Opus.utils.database import record_play
            asyncio.create_task(record_play(user_id, vidid, title, duration, user_name=user))
    
    # Pre-fetch direct URL for the track in background
    async def pre_fetch(c_id, v_id, is_vid):
        if str(v_id).startswith("vortex_"):
            return
        try:
            from Opus import YouTube
            n, link = await YouTube.video(v_id, is_video=is_vid)
            if n == 1:
                # Find the item in queue and update it
                if c_id in db:
                    for item in db[c_id]:
                        if item.get("vidid") == v_id and item.get("file") == f"vid_{v_id}":
                            item["file"] = link
                            break
        except:
            pass

    if vidid and str(file).startswith("vid_"):
        asyncio.create_task(pre_fetch(chat_id, vidid, (stream == "video")))
    autoclean.append(file)


async def put_queue_index(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    stream,
    forceplay: Union[bool, str] = None,
    thumbnail: str = None,
    performer: str = None,
):
    if "20.212.146.162" in vidid:
        try:
            dur = await asyncio.get_event_loop().run_in_executor(
                None, check_duration, vidid
            )
            duration = seconds_to_min(dur)
        except:
            duration = "ᴜʀʟ sᴛʀᴇᴀᴍ"
            dur = 0
    else:
        dur = 0
    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": dur,
        "played": 0,
        "thumb": thumbnail,
        "performer": performer or "Aurex Music",
    }
    if forceplay:
        check = db.get(chat_id)
        if check:
            check.insert(0, put)
        else:
            db[chat_id] = []
            db[chat_id].append(put)
    else:
        db[chat_id].append(put)
