from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def stats_buttons(strings, status):
    not_sudo = [
        InlineKeyboardButton(
            text=strings["SA_B_1"],
            callback_data="TopOverall",
        )
    ]
    sudo = [
        InlineKeyboardButton(
            text=strings["SA_B_2"],
            callback_data="bot_stats_sudo",
        ),
        InlineKeyboardButton(
            text=strings["SA_B_3"],
            callback_data="TopOverall",
        ),
    ]
    upl = InlineKeyboardMarkup(
        [
            sudo if status else not_sudo,
            [
                InlineKeyboardButton(
                    text=strings["CLOSE_BUTTON"],
                    callback_data="close",
                ),
            ],
        ]
    )
    return upl


def back_stats_buttons (strings):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=strings["BACK_BUTTON"],
                    callback_data="stats_back",
                ),
                InlineKeyboardButton(
                    text=strings["CLOSE_BUTTON"],
                    callback_data="close",
                ),
            ],
        ]
    )
    return upl
