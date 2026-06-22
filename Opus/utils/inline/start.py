from pyrogram.types import InlineKeyboardButton

import config
from Opus import app

def start_panel (strings):
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["S_B_1"], url=f"https://t.me/{app.username}?startgroup=true&admin=delete_messages+invite_users"
            ),
            InlineKeyboardButton(text=strings["S_B_2"], url=config.SUPPORT_CHAT),
        ],
    ]
    return buttons


def private_panel (strings):
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["S_B_3"],
                url=f"https://t.me/{app.username}?startgroup=true&admin=delete_messages+invite_users",
            )
        ],
        [
            InlineKeyboardButton(text=strings["S_B_6"], url=config.SUPPORT_CHANNEL),
            InlineKeyboardButton(
                text=strings["S_B_13"],
                url=f"https://t.me/{app.username}?startapp=true",
            ),           
        ],
    ]      
    return buttons
