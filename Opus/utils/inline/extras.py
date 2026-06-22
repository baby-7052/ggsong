from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import SUPPORT_CHAT


def botplaylist_markup(strings):
    buttons = [
        [
            InlineKeyboardButton(text=strings["S_B_9"], url=SUPPORT_CHAT),
            InlineKeyboardButton(text=strings["CLOSE_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


def close_markup(strings):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=strings["CLOSE_BUTTON"],
                    callback_data="close",
                ),
            ]
        ]
    )
    return upl


def supp_markup(strings):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=strings["S_B_9"],
                    url=SUPPORT_CHAT,
                ),
            ]
        ]
    )
    return upl
