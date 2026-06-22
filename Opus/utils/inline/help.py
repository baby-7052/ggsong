from typing import Union

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Opus import app


def help_pannel(strings, START: Union[bool, int] = None):
    first = [InlineKeyboardButton(text=strings["CLOSE_BUTTON"], callback_data=f"close")]
    second = [
        InlineKeyboardButton(
            text=strings["BACK_BUTTON"],
            callback_data=f"settingsback_helper",
        ),
    ]
    mark = second if START else first
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=strings["H_B_1"],
                    callback_data="help_callback hb1",
                ),
            ],      
            [
                InlineKeyboardButton(
                    text=strings["H_B_2"],
                    callback_data="help_callback hb2",
                ),
                InlineKeyboardButton(
                    text=strings["H_B_3"],
                    callback_data="help_callback hb3",
                ),
                InlineKeyboardButton(
                    text=strings["H_B_4"],
                    callback_data="help_callback hb4",
                ),                
            ],
            [
                InlineKeyboardButton(
                    text=strings["H_B_5"],
                    callback_data="help_callback hb5",
                ),
                InlineKeyboardButton(
                    text=strings["H_B_6"],
                    callback_data="help_callback hb6",
                ),  
                InlineKeyboardButton(
                    text=strings["H_B_7"],
                    callback_data="help_callback hb7",
                ),                
            ],

            [
                InlineKeyboardButton(
                    text=strings["H_B_8"],
                    callback_data="help_callback hb8",
                ),                
            ],
            mark,
        ]
    )
    return upl


def help_back_markup(strings):
    upl = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=strings["BACK_BUTTON"],
                    callback_data=f"settings_back_helper",
                ),
            ]
        ]
    )
    return upl


def private_help_panel (strings):
    buttons = [
        [
            InlineKeyboardButton(
                text=strings["S_B_4"],
                url=f"https://t.me/{app.username}?start=help",
            ),
        ],
    ]
    return buttons
