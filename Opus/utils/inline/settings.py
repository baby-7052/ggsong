from typing import Union

from pyrogram.types import InlineKeyboardButton


def setting_markup(strings):
    buttons = [
        [
            InlineKeyboardButton(text=strings["ST_B_1"], callback_data="AU"),
            InlineKeyboardButton(text=strings["ST_B_3"], callback_data="LG"),
        ],
        [
            InlineKeyboardButton(text=strings["ST_B_2"], callback_data="PM"),
        ],
        [
            InlineKeyboardButton(text=strings["ST_B_4"], callback_data="VM"),
        ],
        [
            InlineKeyboardButton(text=strings["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


def vote_mode_markup(strings, current, mode: Union[bool, str] = None):
    buttons = [
        [
            InlineKeyboardButton(text="Vᴏᴛɪɴɢ ᴍᴏᴅᴇ ➜", callback_data="VOTEANSWER"),
            InlineKeyboardButton(
                text=strings["ST_B_5"] if mode == True else strings["ST_B_6"],
                callback_data="VOMODECHANGE",
            ),
        ],
        [
            InlineKeyboardButton(text="-2", callback_data="FERRARIUDTI M"),
            InlineKeyboardButton(
                text=f"ᴄᴜʀʀᴇɴᴛ : {current}",
                callback_data="ANSWERVOMODE",
            ),
            InlineKeyboardButton(text="+2", callback_data="FERRARIUDTI A"),
        ],
        [
            InlineKeyboardButton(
                text=strings["BACK_BUTTON"],
                callback_data="settings_helper",
            ),
            InlineKeyboardButton(text=strings["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


def auth_users_markup(strings, status: Union[bool, str] = None):
    buttons = [
        [
            InlineKeyboardButton(text=strings["ST_B_7"], callback_data="AUTHANSWER"),
            InlineKeyboardButton(
                text=strings["ST_B_8"] if status == True else strings["ST_B_9"],
                callback_data="AUTH",
            ),
        ],
        [
            InlineKeyboardButton(text=strings["ST_B_1"], callback_data="AUTHLIST"),
        ],
        [
            InlineKeyboardButton(
                text=strings["BACK_BUTTON"],
                callback_data="settings_helper",
            ),
            InlineKeyboardButton(text=strings["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


def playmode_users_markup(
    strings,
    Direct: Union[bool, str] = None,
    Group: Union[bool, str] = None,
    Playtype: Union[bool, str] = None,
    Autoplay: Union[bool, str] = None,
    SyncLyrics: Union[bool, str] = None,
):
    buttons = [
        [
            InlineKeyboardButton(text=strings["ST_B_10"], callback_data="SEARCHANSWER"),
            InlineKeyboardButton(
                text=strings["ST_B_11"] if Direct == True else strings["ST_B_12"],
                callback_data="MODECHANGE",
            ),
        ],
        [
            InlineKeyboardButton(text=strings["ST_B_13"], callback_data="AUTHANSWER"),
            InlineKeyboardButton(
                text=strings["ST_B_8"] if Group == True else strings["ST_B_9"],
                callback_data="CHANNELMODECHANGE",
            ),
        ],
        [
            InlineKeyboardButton(text=strings["ST_B_14"], callback_data="PLAYTYPEANSWER"),
            InlineKeyboardButton(
                text=strings["ST_B_8"] if Playtype == True else strings["ST_B_9"],
                callback_data="PLAYTYPECHANGE",
            ),
        ],
        [
            InlineKeyboardButton(text=strings["ST_B_21"], callback_data="AUTOPLAYANSWER"),
            InlineKeyboardButton(
                text=strings["ST_B_5"] if Autoplay == True else strings["ST_B_6"],
                callback_data="AUTOPLAYCHANGE",
            ),
        ],
        [
            InlineKeyboardButton(text="sʏɴᴄ ʟʏʀɪᴄs 🎙️", callback_data="SYNCLYRICSANSWER"),
            InlineKeyboardButton(
                text=strings["ST_B_5"] if SyncLyrics == True else strings["ST_B_6"],
                callback_data="SYNCLYRICSCHANGE",
            ),
        ],
        [
            InlineKeyboardButton(
                text=strings["BACK_BUTTON"],
                callback_data="settings_helper",
            ),
            InlineKeyboardButton(text=strings["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons

def audio_quality_markup(
    strings,
    low: Union[bool, str] = None,
    medium: Union[bool, str] = None,
    high: Union[bool, str] = None,
):
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["ST_B_8"].format("✅")
                if low == True
                else strings["ST_B_8"].format(""),
                callback_data="PulseAudio",
            )
        ],
        [
            InlineKeyboardButton(
                text=strings["ST_B_9"].format("✅")
                if medium == True
                else strings["ST_B_9"].format(""),
                callback_data="TrueBass",
            )
        ],
        [
            InlineKeyboardButton(
                text=strings["ST_B_10"].format("✅")
                if high == True
                else strings["ST_B_10"].format(""),
                callback_data="Dolby",
            )
        ],
        [
            InlineKeyboardButton(
                text=strings["BACK_BUTTON"],
                callback_data="settingsback_helper",
            ),
            InlineKeyboardButton(
                text=strings["CLOSE_BUTTON"], callback_data="close"
            ),
        ],
    ]
    return buttons

def cleanmode_settings_markup(
    strings,
    status: Union[bool, str] = None,
    dels: Union[bool, str] = None,
):
    buttons = [
        [
            InlineKeyboardButton(text=strings["ST_B_7"], callback_data="CMANSWER"),
            InlineKeyboardButton(
                text=strings["ST_B_19"] if status == True else strings["ST_B_20"],
                callback_data="CLEANMODE",
            ),
        ],
        [
            InlineKeyboardButton(text=strings["ST_B_31"], callback_data="COMMANDANSWER"),
            InlineKeyboardButton(
                text=strings["ST_B_19"] if dels == True else strings["ST_B_20"],
                callback_data="COMMANDELMODE",
            ),
        ],
        [
            InlineKeyboardButton(
                text=strings["BACK_BUTTON"],
                callback_data="settingsback_helper",
            ),
            InlineKeyboardButton(text=strings["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons

def video_quality_markup(
    strings,
    low: Union[bool, str] = None,
    medium: Union[bool, str] = None,
    high: Union[bool, str] = None,
):
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["ST_B_11"].format("✅")
                if low == True
                else strings["ST_B_11"].format(""),
                callback_data="FHD-1K",
            )
        ],
        [
            InlineKeyboardButton(
                text=strings["ST_B_12"].format("✅")
                if medium == True
                else strings["ST_B_12"].format(""),
                callback_data="QuadHD-2K",
            )
        ],
        [
            InlineKeyboardButton(
                text=strings["ST_B_13"].format("✅")
                if high == True
                else strings["ST_B_13"].format(""),
                callback_data="UltraHD-4K",
            )
        ],
        [
            InlineKeyboardButton(
                text=strings["BACK_BUTTON"],
                callback_data="settingsback_helper",
            ),
            InlineKeyboardButton(
                text=strings["CLOSE_BUTTON"], callback_data="close"
            ),
        ],
    ]
    return buttons
