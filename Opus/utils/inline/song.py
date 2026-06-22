from pyrogram.types import InlineKeyboardButton


def song_markup(strings, vidid):
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["SG_B_2"],
                callback_data=f"song_helper audio|{vidid}",
            ),
            InlineKeyboardButton(
                text=strings["SG_B_3"],
                callback_data=f"song_helper video|{vidid}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=strings["CLOSE_BUTTON"], callback_data="close"
            ),
        ],
    ]
    return buttons
