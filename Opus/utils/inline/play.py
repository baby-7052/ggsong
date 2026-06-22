import math
from Opus import app
from config import SUPPORT_CHAT, OWNER_ID
from Opus.utils.formatters import time_to_seconds
from pyrogram.types import InlineKeyboardButton


def track_markup(strings, videoid, user_id, channel, fplay, show_lyrics=True, lyric_url=None):
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=strings["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            )
        ],
        [
            InlineKeyboardButton(
                text="ᴏᴡɴᴇʀ 🥀", url=f"tg://openmessage?user_id={OWNER_ID}",
            ),
            InlineKeyboardButton(
                text="sᴜᴩᴩᴏʀᴛ 🥀", url=SUPPORT_CHAT,
            )
        ],
        [
            InlineKeyboardButton(
                text=strings["UPNEXT_BUTTON"],
                callback_data=f"GetUpNext {videoid}|{user_id}|{channel}|{fplay}",
            )
        ],
    ]
    
    last_row = [InlineKeyboardButton(text="ꜜ", callback_data=f"SaveStream {videoid}")]
    buttons.append(last_row)
    return buttons

def telegram_markup(strings, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text="ᴍᴇɴᴜ 📄",
                callback_data=f"PanelMarkup None|{chat_id}",
            ),
            InlineKeyboardButton(
                text=strings["CLOSEMENU_BUTTON"], callback_data="close"
            ),
        ],
    ]
    return buttons

def stream_markup_timer(strings, videoid, chat_id, played, dur, liked=None, lyric_line=None, show_lyrics=True, lyric_url=None):
    if lyric_line:
        bar_text = lyric_line
    else:
        played_sec = time_to_seconds(played)
        duration_sec = time_to_seconds(dur) or 0

        if duration_sec > 0:
            percentage = (played_sec / duration_sec) * 100
        else:
            percentage = 0

        umm = max(0, min(100, math.floor(percentage)))

        total = 10
        pos = round((umm / 100) * total)

        filled = "●" * pos
        empty = "○" * (total - pos)

        bar = f"{filled}{empty}"
        bar_text = f"{played} {bar} {dur}"

    heart = "+"
    buttons = [
        [
            InlineKeyboardButton(
                text=bar_text,
                callback_data="GetTimer",
            )
        ],
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
            InlineKeyboardButton(text=heart, callback_data=f"PlaylistToggle {videoid}"),
        ],
    ]
    
    last_row = [
        InlineKeyboardButton(text="sᴀᴠᴇ", callback_data=f"SaveStream {videoid}"),
        InlineKeyboardButton(text="ꜱʜᴀʀᴇ ᴄᴀʀᴅ", callback_data=f"ShareLyricCard {videoid}")
    ]
    buttons.append(last_row)
    return buttons



def stream_markup(strings, videoid, chat_id, liked=None, show_lyrics=True, lyric_url=None):
    heart = "+"
    buttons = [
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
            InlineKeyboardButton(text=heart, callback_data=f"PlaylistToggle {videoid}"),
        ],
    ]
    
    last_row = [
        InlineKeyboardButton(text="sᴀᴠᴇ", callback_data=f"SaveStream {videoid}"),
        InlineKeyboardButton(text="ꜱʜᴀʀᴇ ᴄᴀʀᴅ", callback_data=f"ShareLyricCard {videoid}")
    ]
    buttons.append(last_row)
    return buttons

def stream_markup_autoplay(strings, videoid, chat_id, autoplay_status, liked=None, show_lyrics=True, lyric_url=None):
    heart = "+"
    buttons = [
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
            InlineKeyboardButton(text=heart, callback_data=f"PlaylistToggle {videoid}"),
        ],
        [
            InlineKeyboardButton(
                text=strings["AUTOPLAY_ON"] if autoplay_status else strings["AUTOPLAY_OFF"],
                callback_data=f"AutoplayToggle {chat_id}",
            )
        ],
    ]
    
    last_row = [
        InlineKeyboardButton(text="sᴀᴠᴇ", callback_data=f"SaveStream {videoid}"),
        InlineKeyboardButton(text="ꜱʜᴀʀᴇ ᴄᴀʀᴅ", callback_data=f"ShareLyricCard {videoid}")
    ]
    buttons.append(last_row)
    return buttons


def playlist_markup(strings, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["P_B_1"],
                callback_data=f"OpusPlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=strings["P_B_2"],
                callback_data=f"OpusPlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=strings["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]
    return buttons


def livestream_markup(strings, videoid, user_id, mode, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["P_B_3"],
                callback_data=f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=strings["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]
    return buttons


def slider_markup(strings, videoid, user_id, query, query_type, channel, fplay):
    query = f"{query[:20]}"
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=strings["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=f"slider B|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=strings["CLOSE_BUTTON"],
                callback_data=f"forceclose {query}|{user_id}",
            ),
            InlineKeyboardButton(
                text="▷",
                callback_data=f"slider F|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
        ],
    ]
    return buttons

def stream_markup2(strings, videoid, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text="▷",
                callback_data=f"ADMIN Resume|{chat_id}",
            ),
            InlineKeyboardButton(
                text="II", callback_data=f"ADMIN Pause|{chat_id}"
            ),
            InlineKeyboardButton(
                text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"
            ),
            InlineKeyboardButton(
                text="▢", callback_data=f"ADMIN Stop|{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="ᴏᴡɴᴇʀ 🥀", url=f"tg://openmessage?user_id={OWNER_ID}",
            ),
            InlineKeyboardButton(
                text="sᴜᴘᴘᴏʀᴛ 💘",
                url=SUPPORT_CHAT,
            ),
        ],
        [
            InlineKeyboardButton(
                text="sʜᴜғғʟᴇ 🔀",
                callback_data=f"ADMIN Shuffle|{chat_id}",
            ),
            InlineKeyboardButton(
                text="ʟᴏᴏᴩ ➿", callback_data=f"ADMIN Loop|{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=strings["UPNEXT_BUTTON"],
                callback_data=f"GetUpNext {videoid}|{chat_id}|None|None",
            )
        ],
        [
             InlineKeyboardButton(
                text="ᴀᴜᴛᴏᴘʟᴀʏ",
                callback_data=f"AutoplayToggle {chat_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="ʙᴀᴄᴋ 🔙",
                callback_data=f"MainMarkup {videoid}|{chat_id}",
            ),
        ],
    ]
    return buttons
def upnext_markup(strings, user_id, channel, fplay, suggestions, videoid, offset=0):
    buttons = []

    limit = 4
    for s in suggestions[offset : offset + limit]:
        title = s.get('title') or s.get('name') or "Unknown Track"

        import re
        title = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()

        if " - " in title:
            parts = title.split(" - ")

            title = parts[1] if len(parts) > 1 else parts[0]
        

        title = (title[:22] + "..") if len(title) > 22 else title
        
        buttons.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"MusicStream {s['id']}|{user_id}|a|{channel}|{fplay}",
                )
            ]
        )
    

    if len(suggestions) > offset + limit:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="ʟᴏᴀᴅ ᴍᴏʀᴇ 🔄",
                    callback_data=f"LoadMore {videoid}|{user_id}|{channel}|{fplay}|{offset + limit}",
                )
            ]
        )
    
    return buttons
