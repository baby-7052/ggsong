import random
from datetime import datetime
from typing import Dict, List, Union
from collections import OrderedDict

from Opus import userbot
from Opus.core.mongo import mongodb

authdb = mongodb.adminauth
authuserdb = mongodb.authuser
autoenddb = mongodb.autoend
assdb = mongodb.assistants
blacklist_chatdb = mongodb.blacklistChat
blockeddb = mongodb.blockedusers
chatsdb = mongodb.chats
channeldb = mongodb.cplaymode
countdb = mongodb.upcount
gbansdb = mongodb.gban
langdb = mongodb.language
onoffdb = mongodb.onoffper
playmodedb = mongodb.playmode
playtypedb = mongodb.playtypedb
skipdb = mongodb.skipmode
sudoersdb = mongodb.sudoers
usersdb = mongodb.tgusersdb
thumbdb = mongodb.thumb
thumbstyledb = mongodb.thumbstyle
thumbaligndb = mongodb.thumbalign
autoplaydb = mongodb.autoplay
synclyricsdb = mongodb.synclyrics
statsdb = mongodb.stats
playlistdb = mongodb.playlists

class LRUDict(OrderedDict):
    """A memory-bounded dictionary that acts as an LRU Cache."""
    def __init__(self, maxsize=10000, *args, **kwargs):
        self.maxsize = maxsize
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            self.popitem(last=False)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

# Shifting to memory [mongo sucks often]
active = []
activevideo = []
assistantdict = LRUDict(maxsize=10000)
autoend = LRUDict(maxsize=10000)
count = LRUDict(maxsize=10000)
channelconnect = LRUDict(maxsize=10000)
langm = LRUDict(maxsize=10000)
loop = LRUDict(maxsize=10000)
maintenance = []
nonadmin = LRUDict(maxsize=10000)
pause = LRUDict(maxsize=10000)
playmode = LRUDict(maxsize=10000)
playtype = LRUDict(maxsize=10000)
skipmode = LRUDict(maxsize=10000)
thumbmode = LRUDict(maxsize=10000)
thumbstyle = LRUDict(maxsize=10000)
thumbalign = LRUDict(maxsize=10000)
autoplay = LRUDict(maxsize=10000)
synclyrics = LRUDict(maxsize=10000)


async def get_assistant_number(chat_id: int) -> str:
    assistant = assistantdict.get(chat_id)
    return assistant


async def get_client(assistant: int):
    try:
        assis = int(assistant)
    except (ValueError, TypeError):
        return None
    if assis == 1:
        return userbot.one
    elif assis == 2:
        return userbot.two
    elif assis == 3:
        return userbot.three
    elif assis == 4:
        return userbot.four
    elif assis == 5:
        return userbot.five
    return None


async def set_assistant_new(chat_id, number):
    number = int(number)
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": number}},
        upsert=True,
    )


async def set_assistant(chat_id):
    from Opus.core.userbot import assistants
    
    # Smart Load Balancing: Count occurrences of each assistant in current chats
    counts = {a: 0 for a in assistants}
    for a in assistantdict.values():
        if a in counts:
            counts[a] += 1
            
    # Pick the one with the minimum count
    ran_assistant = min(counts, key=counts.get)
    
    assistantdict[chat_id] = ran_assistant
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    userbot = await get_client(ran_assistant)
    return userbot


async def get_assistant(chat_id: int) -> str:
    from Opus.core.userbot import assistants

    assistant = assistantdict.get(chat_id)
    if not assistant:
        dbassistant = await assdb.find_one({"chat_id": chat_id})
        if not dbassistant:
            userbot = await set_assistant(chat_id)
            return userbot
        else:
            got_assis = dbassistant["assistant"]
            if got_assis in assistants:
                assistantdict[chat_id] = got_assis
                userbot = await get_client(got_assis)
                return userbot
            else:
                userbot = await set_assistant(chat_id)
                return userbot
    else:
        if assistant in assistants:
            userbot = await get_client(assistant)
            return userbot
        else:
            userbot = await set_assistant(chat_id)
            return userbot


async def set_calls_assistant(chat_id):
    from Opus.core.userbot import assistants

    # Smart Load Balancing
    counts = {a: 0 for a in assistants}
    for a in assistantdict.values():
        if a in counts:
            counts[a] += 1
            
    ran_assistant = min(counts, key=counts.get)
    
    assistantdict[chat_id] = ran_assistant
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    return ran_assistant


async def group_assistant(self, chat_id: int) -> int:
    from Opus.core.userbot import assistants

    assistant = assistantdict.get(chat_id)
    if not assistant:
        dbassistant = await assdb.find_one({"chat_id": chat_id})
        if not dbassistant:
            assis = await set_calls_assistant(chat_id)
        else:
            assis = dbassistant["assistant"]
            if assis in assistants:
                assistantdict[chat_id] = assis
                assis = assis
            else:
                assis = await set_calls_assistant(chat_id)
    else:
        if assistant in assistants:
            assis = assistant
        else:
            assis = await set_calls_assistant(chat_id)
    try:
        assis = int(assis)
    except (ValueError, TypeError):
        assis = 1
    if assis == 1:
        return self.one
    elif assis == 2:
        return self.two
    elif assis == 3:
        return self.three
    elif assis == 4:
        return self.four
    elif assis == 5:
        return self.five
    return self.one


async def get_thumb_setting(chat_id: int):
    if chat_id in thumbmode:
        return thumbmode[chat_id]
    user = await thumbdb.find_one({"chat_id": chat_id})
    if user:
        thumbmode[chat_id] = user.get("value", True)
        return thumbmode[chat_id]
    thumbmode[chat_id] = True
    return True

async def set_thumb_setting(chat_id: int, value: bool):
    thumbmode[chat_id] = value
    await thumbdb.update_one({"chat_id": chat_id}, {"$set": {"value": value}}, upsert=True)


async def get_thumb_style(chat_id: int) -> int:
    if chat_id in thumbstyle:
        return thumbstyle[chat_id]
    user = await thumbstyledb.find_one({"chat_id": chat_id})
    if user:
        thumbstyle[chat_id] = user.get("style", 1)
        return thumbstyle[chat_id]
    thumbstyle[chat_id] = 1
    return 1


async def set_thumb_style(chat_id: int, style: int):
    thumbstyle[chat_id] = style
    await thumbstyledb.update_one({"chat_id": chat_id}, {"$set": {"style": style}}, upsert=True)


async def get_thumb_align(chat_id: int) -> str:
    if chat_id in thumbalign:
        return thumbalign[chat_id]
    user = await thumbaligndb.find_one({"chat_id": chat_id})
    if user:
        thumbalign[chat_id] = user.get("align", "center")
        return thumbalign[chat_id]
    thumbalign[chat_id] = "center"
    return "center"


async def set_thumb_align(chat_id: int, align: str):
    thumbalign[chat_id] = align
    await thumbaligndb.update_one({"chat_id": chat_id}, {"$set": {"align": align}}, upsert=True)


async def is_skipmode(chat_id: int) -> bool:
    mode = skipmode.get(chat_id)
    if not mode:
        user = await skipdb.find_one({"chat_id": chat_id})
        if not user:
            skipmode[chat_id] = True
            return True
        skipmode[chat_id] = False
        return False
    return mode


async def skip_on(chat_id: int):
    skipmode[chat_id] = True
    user = await skipdb.find_one({"chat_id": chat_id})
    if user:
        return await skipdb.delete_one({"chat_id": chat_id})


async def skip_off(chat_id: int):
    skipmode[chat_id] = False
    user = await skipdb.find_one({"chat_id": chat_id})
    if not user:
        return await skipdb.insert_one({"chat_id": chat_id})


async def get_upvote_count(chat_id: int) -> int:
    mode = count.get(chat_id)
    if not mode:
        mode = await countdb.find_one({"chat_id": chat_id})
        if not mode:
            return 5
        count[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_upvotes(chat_id: int, mode: int):
    count[chat_id] = mode
    await countdb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def is_autoend(chat_id: int) -> bool:
    user = await autoenddb.find_one({"chat_id": chat_id})
    if not user:
        return False
    return True


async def autoend_on(chat_id: int):
    await autoenddb.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)


async def autoend_off(chat_id: int):
    await autoenddb.delete_many({"chat_id": chat_id})


async def get_loop(chat_id: int) -> int:
    lop = loop.get(chat_id)
    if not lop:
        return 0
    return lop


async def set_loop(chat_id: int, mode: int):
    loop[chat_id] = mode


async def get_cmode(chat_id: int) -> int:
    mode = channelconnect.get(chat_id)
    if not mode:
        mode = await channeldb.find_one({"chat_id": chat_id})
        if not mode:
            return None
        channelconnect[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_cmode(chat_id: int, mode: int):
    channelconnect[chat_id] = mode
    await channeldb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playtype(chat_id: int) -> str:
    mode = playtype.get(chat_id)
    if not mode:
        mode = await playtypedb.find_one({"chat_id": chat_id})
        if not mode:
            playtype[chat_id] = "Everyone"
            return "Everyone"
        playtype[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_playtype(chat_id: int, mode: str):
    playtype[chat_id] = mode
    await playtypedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playmode(chat_id: int) -> str:
    mode = playmode.get(chat_id)
    if not mode:
        mode = await playmodedb.find_one({"chat_id": chat_id})
        if not mode:
            playmode[chat_id] = "Direct"
            return "Direct"
        playmode[chat_id] = mode["mode"]
        return mode["mode"]
    return mode


async def set_playmode(chat_id: int, mode: str):
    playmode[chat_id] = mode
    await playmodedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_lang(chat_id: int) -> str:
    mode = langm.get(chat_id)
    if not mode:
        lang = await langdb.find_one({"chat_id": chat_id})
        if not lang:
            langm[chat_id] = "en"
            return "en"
        langm[chat_id] = lang["lang"]
        return lang["lang"]
    return mode


async def set_lang(chat_id: int, lang: str):
    langm[chat_id] = lang
    await langdb.update_one({"chat_id": chat_id}, {"$set": {"lang": lang}}, upsert=True)


async def is_music_playing(chat_id: int) -> bool:
    mode = pause.get(chat_id)
    if not mode:
        return False
    return mode


async def music_on(chat_id: int):
    pause[chat_id] = True


async def music_off(chat_id: int):
    pause[chat_id] = False


async def get_active_chats() -> list:
    return active


async def is_active_chat(chat_id: int) -> bool:
    if chat_id not in active:
        return False
    else:
        return True


async def add_active_chat(chat_id: int):
    if chat_id not in active:
        active.append(chat_id)


async def remove_active_chat(chat_id: int):
    if chat_id in active:
        active.remove(chat_id)


async def get_active_video_chats() -> list:
    return activevideo


async def is_active_video_chat(chat_id: int) -> bool:
    if chat_id not in activevideo:
        return False
    else:
        return True


async def add_active_video_chat(chat_id: int):
    if chat_id not in activevideo:
        activevideo.append(chat_id)


async def remove_active_video_chat(chat_id: int):
    if chat_id in activevideo:
        activevideo.remove(chat_id)


async def check_nonadmin_chat(chat_id: int) -> bool:
    user = await authdb.find_one({"chat_id": chat_id})
    if not user:
        return False
    return True


async def is_nonadmin_chat(chat_id: int) -> bool:
    mode = nonadmin.get(chat_id)
    if not mode:
        user = await authdb.find_one({"chat_id": chat_id})
        if not user:
            nonadmin[chat_id] = True
            return True
        nonadmin[chat_id] = True
        return True
    return mode


async def add_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = True
    is_admin = await check_nonadmin_chat(chat_id)
    if is_admin:
        return
    return await authdb.insert_one({"chat_id": chat_id})


async def remove_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = False
    is_admin = await check_nonadmin_chat(chat_id)
    if not is_admin:
        return
    return await authdb.delete_one({"chat_id": chat_id})


async def is_on_off(on_off: int) -> bool:
    onoff = await onoffdb.find_one({"on_off": on_off})
    if not onoff:
        return False
    return True


async def add_on(on_off: int):
    is_on = await is_on_off(on_off)
    if is_on:
        return
    return await onoffdb.insert_one({"on_off": on_off})


async def add_off(on_off: int):
    is_off = await is_on_off(on_off)
    if not is_off:
        return
    return await onoffdb.delete_one({"on_off": on_off})


async def is_maintenance():
    if not maintenance:
        get = await onoffdb.find_one({"on_off": 1})
        if not get:
            maintenance.clear()
            maintenance.append(2)
            return True
        else:
            maintenance.clear()
            maintenance.append(1)
            return False
    else:
        if 1 in maintenance:
            return False
        else:
            return True


async def maintenance_off():
    maintenance.clear()
    maintenance.append(2)
    is_off = await is_on_off(1)
    if not is_off:
        return
    return await onoffdb.delete_one({"on_off": 1})


async def maintenance_on():
    maintenance.clear()
    maintenance.append(1)
    is_on = await is_on_off(1)
    if is_on:
        return
    return await onoffdb.insert_one({"on_off": 1})


async def is_served_user(user_id: int) -> bool:
    user = await usersdb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def get_served_users() -> list:
    users_list = []
    async for user in usersdb.find({"user_id": {"$gt": 0}}):
        users_list.append(user)
    return users_list


async def add_served_user(user_id: int):
    is_served = await is_served_user(user_id)
    if is_served:
        return
    return await usersdb.insert_one({"user_id": user_id})


async def get_served_chats() -> list:
    chats_list = []
    async for chat in chatsdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat)
    return chats_list


async def is_served_chat(chat_id: int) -> bool:
    chat = await chatsdb.find_one({"chat_id": chat_id})
    if not chat:
        return False
    return True


async def add_served_chat(chat_id: int):
    is_served = await is_served_chat(chat_id)
    if is_served:
        return
    return await chatsdb.insert_one({"chat_id": chat_id})


async def blacklisted_chats() -> list:
    chats_list = []
    async for chat in blacklist_chatdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat["chat_id"])
    return chats_list


async def blacklist_chat(chat_id: int) -> bool:
    if not await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.insert_one({"chat_id": chat_id})
        return True
    return False


async def whitelist_chat(chat_id: int) -> bool:
    if await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.delete_one({"chat_id": chat_id})
        return True
    return False


async def _get_authusers(chat_id: int) -> Dict[str, int]:
    _notes = await authuserdb.find_one({"chat_id": chat_id})
    if not _notes:
        return {}
    return _notes["notes"]


async def get_authuser_names(chat_id: int) -> List[str]:
    _notes = []
    for note in await _get_authusers(chat_id):
        _notes.append(note)
    return _notes


async def get_authuser(chat_id: int, name: str) -> Union[bool, dict]:
    name = name
    _notes = await _get_authusers(chat_id)
    if name in _notes:
        return _notes[name]
    else:
        return False


async def save_authuser(chat_id: int, name: str, note: dict):
    name = name
    _notes = await _get_authusers(chat_id)
    _notes[name] = note

    await authuserdb.update_one(
        {"chat_id": chat_id}, {"$set": {"notes": _notes}}, upsert=True
    )


async def delete_authuser(chat_id: int, name: str) -> bool:
    notesd = await _get_authusers(chat_id)
    name = name
    if name in notesd:
        del notesd[name]
        await authuserdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": notesd}},
            upsert=True,
        )
        return True
    return False


async def get_gbanned() -> list:
    results = []
    async for user in gbansdb.find({"user_id": {"$gt": 0}}):
        user_id = user["user_id"]
        results.append(user_id)
    return results


async def is_gbanned_user(user_id: int) -> bool:
    user = await gbansdb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def add_gban_user(user_id: int):
    is_gbanned = await is_gbanned_user(user_id)
    if is_gbanned:
        return
    return await gbansdb.insert_one({"user_id": user_id})


async def remove_gban_user(user_id: int):
    is_gbanned = await is_gbanned_user(user_id)
    if not is_gbanned:
        return
    return await gbansdb.delete_one({"user_id": user_id})


async def get_sudoers() -> list:
    sudoers = await sudoersdb.find_one({"sudo": "sudo"})
    if not sudoers:
        return []
    return sudoers["sudoers"]


async def add_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    sudoers.append(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


async def remove_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    sudoers.remove(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


async def get_banned_users() -> list:
    results = []
    async for user in blockeddb.find({"user_id": {"$gt": 0}}):
        user_id = user["user_id"]
        results.append(user_id)
    return results


async def get_banned_count() -> int:
    users = blockeddb.find({"user_id": {"$gt": 0}})
    users = await users.to_list(length=100000)
    return len(users)


async def is_banned_user(user_id: int) -> bool:
    user = await blockeddb.find_one({"user_id": user_id})
    if not user:
        return False
    return True


async def add_banned_user(user_id: int):
    is_gbanned = await is_banned_user(user_id)
    if is_gbanned:
        return
    return await blockeddb.insert_one({"user_id": user_id})


async def remove_banned_user(user_id: int):
    is_gbanned = await is_banned_user(user_id)
    if not is_gbanned:
        return
    return await blockeddb.delete_one({"user_id": user_id})


async def is_autoplay(chat_id: int) -> bool:
    mode = autoplay.get(chat_id)
    if mode is None:
        user = await autoplaydb.find_one({"chat_id": chat_id})
        if not user:
            autoplay[chat_id] = False
            return False
        autoplay[chat_id] = True
        return True
    return mode


async def autoplay_on(chat_id: int):
    autoplay[chat_id] = True
    user = await autoplaydb.find_one({"chat_id": chat_id})
    if not user:
        return await autoplaydb.insert_one({"chat_id": chat_id})


async def autoplay_off(chat_id: int):
    autoplay[chat_id] = False
    user = await autoplaydb.find_one({"chat_id": chat_id})
    if user:
        return await autoplaydb.delete_one({"chat_id": chat_id})


async def is_sync_lyrics(chat_id: int) -> bool:
    mode = synclyrics.get(chat_id)
    if mode is None:
        user = await synclyricsdb.find_one({"chat_id": chat_id})
        if not user:
            synclyrics[chat_id] = False
            return False
        synclyrics[chat_id] = True
        return True
    return mode


async def sync_lyrics_on(chat_id: int):
    synclyrics[chat_id] = True
    user = await synclyricsdb.find_one({"chat_id": chat_id})
    if not user:
        return await synclyricsdb.insert_one({"chat_id": chat_id})


async def sync_lyrics_off(chat_id: int):
    synclyrics[chat_id] = False
    user = await synclyricsdb.find_one({"chat_id": chat_id})
    if user:
        return await synclyricsdb.delete_one({"chat_id": chat_id})

# ----------------- WRAPPED / STATS ----------------- #

async def record_play(user_id: int, vidid: str, title: str, duration_min: str, user_name: str = None):
    # Atomic instant increment for blazing fast database updates
    now = datetime.utcnow()
    day_key = now.strftime("%Y-%m-%d")
    week_key = now.strftime("%Y-W%W")
    month_key = now.strftime("%Y-%m")
    
    update_ops = {
        "$inc": {
            "total_played": 1,
            f"tracks.{vidid}.count": 1,
            f"periods.daily.{day_key}": 1,
            f"periods.weekly.{week_key}": 1,
            f"periods.monthly.{month_key}": 1
        },
        "$set": {
            f"tracks.{vidid}.title": title
        }
    }
    
    if user_name:
        update_ops["$set"]["user_name"] = user_name
        
    await statsdb.update_one(
        {"user_id": user_id},
        update_ops,
        upsert=True
    )

async def get_user_stats(user_id: int) -> dict:
    user_stats = await statsdb.find_one({"user_id": user_id})
    return user_stats if user_stats else None

async def get_leaderboard(period: str = "all", limit: int = 10) -> list:
    """Fetch top users sorted by play count for a given period.
    period: 'all', 'monthly', 'weekly', 'today'
    Returns list of dicts: [{ 'user_id', 'total_played', 'period_plays', 'tracks' }, ...]
    """
    now = datetime.utcnow()
    results = []
    
    # Use native MongoDB sorting for blazing fast fetches
    if period == "all":
        sort_key = "total_played"
        query = {"total_played": {"$gt": 0}}
    else:
        if period == "today":
            date_key = now.strftime("%Y-%m-%d")
            sort_key = f"periods.daily.{date_key}"
        elif period == "weekly":
            date_key = now.strftime("%Y-W%W")
            sort_key = f"periods.weekly.{date_key}"
        elif period == "monthly":
            date_key = now.strftime("%Y-%m")
            sort_key = f"periods.monthly.{date_key}"
        else:
            sort_key = "total_played"
            
        query = {sort_key: {"$gt": 0}}
        
    cursor = statsdb.find(query).sort(sort_key, -1).limit(limit)
    
    async for doc in cursor:
        user_id = doc.get("user_id")
        if not user_id:
            continue
            
        if period == "all":
            play_count = doc.get("total_played", 0)
        else:
            periods = doc.get("periods", {})
            if period == "today":
                play_count = periods.get("daily", {}).get(date_key, 0)
            elif period == "weekly":
                play_count = periods.get("weekly", {}).get(date_key, 0)
            elif period == "monthly":
                play_count = periods.get("monthly", {}).get(date_key, 0)
            else:
                play_count = doc.get("total_played", 0)
                
        results.append({
            "user_id": user_id,
            "total_played": doc.get("total_played", 0),
            "period_plays": play_count,
            "tracks": doc.get("tracks", {})
        })
        
    return results

# ----------------- QUEUE PERSISTENCE ----------------- #

queuedb = mongodb.queue

async def persist_queue(chat_id: int, queue: list):
    # We only save necessary info for persistence
    # We remove 'mystic' as it's a message object that can't be pickled/saved easily
    serializable_queue = []
    for item in queue:
        new_item = item.copy()
        if "mystic" in new_item:
            del new_item["mystic"]
        serializable_queue.append(new_item)
        
    await queuedb.update_one(
        {"chat_id": chat_id},
        {"$set": {"queue": serializable_queue}},
        upsert=True
    )

async def clear_persisted_queue(chat_id: int):
    await queuedb.delete_one({"chat_id": chat_id})

async def get_persisted_queues() -> dict:
    queues = {}
    async for doc in queuedb.find():
        queues[doc["chat_id"]] = doc["queue"]
    return queues


playlistdb = mongodb.playlists

async def get_playlist(user_id: int) -> list:
    playlist = await playlistdb.find_one({"user_id": user_id})
    if playlist:
        return playlist.get("playlist", [])
    return []

async def add_to_playlist(user_id: int, song_data: dict):
    # Ensure no duplicates in personal playlist based on vidid
    playlist = await get_playlist(user_id)
    if any(s['vidid'] == song_data['vidid'] for s in playlist):
        return False
    
    await playlistdb.update_one(
        {"user_id": user_id},
        {"$push": {"playlist": song_data}},
        upsert=True,
    )
    return True

async def remove_from_playlist(user_id: int, vidid: str):
    await playlistdb.update_one(
        {"user_id": user_id},
        {"$pull": {"playlist": {"vidid": vidid}}},
    )

async def is_on_playlist(user_id: int, vidid: str) -> bool:
    playlist = await playlistdb.find_one({"user_id": user_id, "playlist.vidid": vidid})
    return True if playlist else False

async def clear_playlist(user_id: int):
    await playlistdb.delete_one({"user_id": user_id})


async def deduplicate_collection(collection, key):
    """Deletes duplicate documents in a collection based on a key, keeping only the first one found."""
    try:
        cursor = collection.aggregate([
            {"$group": {
                "_id": f"${key}",
                "uniqueIds": {"$push": "$_id"},
                "count": {"$sum": 1}
            }},
            {"$match": {
                "count": {"$gt": 1}
            }}
        ])
        
        duplicates_removed = 0
        async for doc in cursor:
            # Keep the first _id and delete the rest
            ids_to_delete = doc["uniqueIds"][1:]
            res = await collection.delete_many({"_id": {"$in": ids_to_delete}})
            duplicates_removed += res.deleted_count
            
        if duplicates_removed > 0:
            from Opus.logging import LOGGER
            LOGGER("Opus.database").info(f"[bold cyan]● DATABASE[/bold cyan] | Deduplicated {collection.name}: removed {duplicates_removed} redundant records.")
    except Exception as e:
        print(f"⚠️ [Database] Deduplication error for {collection.name}: {e}")


async def init_database_indexes():
    """Create unique indexes on chat_id/user_id for all MongoDB collections to enable O(1) lookups."""
    # We define a mapping of collection to key and whether it is unique
    indexes_to_create = [
        (authdb, "chat_id", True),
        (authuserdb, "chat_id", True),
        (autoenddb, "chat_id", True),
        (assdb, "chat_id", True),
        (blacklist_chatdb, "chat_id", True),
        (blockeddb, "user_id", True),
        (chatsdb, "chat_id", True),
        (channeldb, "chat_id", True),
        (countdb, "chat_id", True),
        (gbansdb, "user_id", True),
        (langdb, "chat_id", True),
        (playmodedb, "chat_id", True),
        (playtypedb, "chat_id", True),
        (skipdb, "chat_id", True),
        (usersdb, "user_id", True),
        (thumbdb, "chat_id", True),
        (thumbstyledb, "chat_id", True),
        (thumbaligndb, "chat_id", True),
        (autoplaydb, "chat_id", True),
        (synclyricsdb, "chat_id", True),
        (statsdb, "user_id", True),
        (statsdb, "total_played", False), # sorting index
        (playlistdb, "user_id", True),
        (queuedb, "chat_id", True),
    ]
    
    for collection, field, unique in indexes_to_create:
        try:
            if field == "total_played":
                await collection.create_index([(field, -1)], unique=unique, background=True)
            else:
                await collection.create_index([(field, 1)], unique=unique, background=True)
        except Exception as e:
            # Handle duplicate key errors by self-healing (deduplicating) the collection and retrying!
            if "duplicate key" in str(e).lower() or "11000" in str(e):
                await deduplicate_collection(collection, field)
                try:
                    if field == "total_played":
                        await collection.create_index([(field, -1)], unique=unique, background=True)
                    else:
                        await collection.create_index([(field, 1)], unique=unique, background=True)
                except Exception as e_retry:
                    print(f"⚠️ [Database] Failed to build index on {collection.name} after deduplication: {e_retry}")
            else:
                print(f"⚠️ [Database] Index initialization warning for {collection.name}: {e}")

    from Opus.logging import LOGGER
    LOGGER("Opus.database").info("[bold cyan]● DATABASE[/bold cyan] | MongoDB collection indexes initialized.")
