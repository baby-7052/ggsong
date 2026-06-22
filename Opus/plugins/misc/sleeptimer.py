import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from Opus import app
import Opus.core.call as core_call
from Opus.utils.database import is_music_playing, music_off, get_lang, get_client, group_assistant
from Opus.utils.decorators import AdminRightsCheck, ActualAdminCB
from config import BANNED_USERS
from strings import get_string

# In-memory storage for active timers
timer = {}
sleep_timer_val = {}

def sleep_timer_markup(active_minutes: int = 0):
    """Generates the interactive inline keyboard grid for the sleep timer."""
    buttons = [
        [
            InlineKeyboardButton("15 ᴍɪɴs" if active_minutes != 15 else "• 15 ᴍɪɴs •", callback_data="sleep_set_15"),
            InlineKeyboardButton("30 ᴍɪɴs" if active_minutes != 30 else "• 30 ᴍɪɴs •", callback_data="sleep_set_30"),
            InlineKeyboardButton("45 ᴍɪɴs" if active_minutes != 45 else "• 45 ᴍɪɴs •", callback_data="sleep_set_45"),
        ],
        [
            InlineKeyboardButton("60 ᴍɪɴs" if active_minutes != 60 else "• 60 ᴍɪɴs •", callback_data="sleep_set_60"),
            InlineKeyboardButton("90 ᴍɪɴs" if active_minutes != 90 else "• 90 ᴍɪɴs •", callback_data="sleep_set_90"),
        ]
    ]
    if active_minutes > 0:
        buttons.append([
            InlineKeyboardButton("🚫 ᴄᴀɴᴄᴇʟ ᴛɪᴍᴇʀ", callback_data="sleep_set_cancel")
        ])
    buttons.append([
        InlineKeyboardButton("🗑 ᴄʟᴏsᴇ", callback_data="sleep_set_close")
    ])
    return InlineKeyboardMarkup(buttons)


@app.on_message(filters.command(["sleeptimer", "stopafter"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def sleep_timer_set(client, message: Message, _, chat_id):
    # Language and strings
    language = await get_lang(chat_id)
    
    # Check if music is actually playing
    if not await is_music_playing(chat_id):
        return await message.reply_text(_["sleep_6"])
        
    # If a time duration was provided directly via command (e.g. /sleeptimer 15)
    if len(message.command) == 2:
        try:
            minutes = int(message.command[1])
        except ValueError:
            return await message.reply_text(_["sleep_2"])
            
        if minutes <= 0:
            return await message.reply_text("<blockquote><b>» ᴘʟᴇᴀsᴇ sᴇᴛ ᴀ ᴠᴀʟɪᴅ ᴘᴏsɪᴛɪᴠᴇ ɴᴜᴍʙᴇʀ ᴏғ ᴍɪɴᴜᴛᴇs.</b></blockquote>")

        if chat_id in timer:
            timer[chat_id].cancel()
            
        async def sleep_timer_handler(chat_id, minutes, lang_code):
            try:
                await asyncio.sleep(minutes * 60)
                if await is_music_playing(chat_id):
                    await music_off(chat_id)
                    await core_call.Signal.pause_stream(chat_id, is_auto=True)
                    
                    _inner = get_string(lang_code)
                    buttons = [
                        [
                            InlineKeyboardButton(
                                text=_inner["sleep_5"],
                                callback_data=f"ADMIN Resume|{chat_id}"
                            )
                        ]
                    ]
                    await app.send_message(
                        chat_id,
                        text=_inner["sleep_4"],
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
            except asyncio.CancelledError:
                pass
            finally:
                if chat_id in timer:
                    del timer[chat_id]
                sleep_timer_val[chat_id] = 0
                
        timer[chat_id] = asyncio.create_task(sleep_timer_handler(chat_id, minutes, language))
        sleep_timer_val[chat_id] = minutes
        
        await message.reply_text(_["sleep_3"].format(minutes))
        
        # Verify assistant permissions
        try:
            assistant_num = await group_assistant(core_call.Signal, chat_id)
            assistant_client = await get_client(assistant_num)
            assistant_member = await assistant_client.get_chat_member(chat_id, "me")
            if assistant_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await message.reply_text(_["sleep_7"].format(assistant_num))
        except:
            pass
        return

    # If no argument is passed, display the gorgeous inline panel!
    active_minutes = sleep_timer_val.get(chat_id, 0)
    if active_minutes > 0 and chat_id in timer:
        text = (
            "<blockquote><b>🕒 sʟᴇᴇᴘ ᴛɪᴍᴇʀ ᴘᴀɴᴇʟ</b>\n\n"
            f"» sʟᴇᴇᴘ ᴛɪᴍᴇʀ sᴇᴛ ғᴏʀ <b>{active_minutes} ᴍɪɴᴜᴛᴇs</b>.\n"
            "ᴛʜᴇ sᴛʀᴇᴀᴍ ᴡɪʟʟ ᴘᴀᴜsᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ.</blockquote>"
        )
    else:
        text = (
            "<blockquote><b>🕒 sʟᴇᴇᴘ ᴛɪᴍᴇʀ ᴘᴀɴᴇʟ</b>\n\n"
            "» ᴄʜᴏᴏsᴇ ᴀ ᴅᴜʀᴀᴛɪᴏɴ ᴀғᴛᴇʀ ᴡʜɪᴄʜ ᴛʜᴇ sᴛʀᴇᴀᴍ ᴡɪʟʟ ʙᴇ ᴘᴀᴜsᴇᴅ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ.</blockquote>"
        )
        
    await message.reply_text(
        text=text,
        reply_markup=sleep_timer_markup(active_minutes)
    )


@app.on_callback_query(filters.regex(r"^sleep_set_") & ~BANNED_USERS)
@ActualAdminCB
async def sleep_timer_callback(client, query, _):
    chat_id = query.message.chat.id
    action = query.data.split("_")[2]
    
    language = await get_lang(chat_id)
    _ = get_string(language)
    
    if action == "close":
        try:
            await query.message.delete()
        except:
            pass
        return
        
    if action == "cancel":
        if chat_id in timer:
            timer[chat_id].cancel()
            del timer[chat_id]
        sleep_timer_val[chat_id] = 0
        
        await query.answer("» sʟᴇᴇᴘ ᴛɪᴍᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ 🚫", show_alert=True)
        try:
            await query.message.edit_text(
                "<blockquote><b>🕒 sʟᴇᴇᴘ ᴛɪᴍᴇʀ ᴘᴀɴᴇʟ</b>\n\n» ᴄʜᴏᴏsᴇ ᴀ ᴅᴜʀᴀᴛɪᴏɴ ᴀғᴛᴇʀ ᴡʜɪᴄʜ ᴛʜᴇ sᴛʀᴇᴀᴍ ᴡɪʟʟ ʙᴇ ᴘᴀᴜsᴇᴅ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ.</blockquote>",
                reply_markup=sleep_timer_markup(0)
            )
        except:
            pass
        return
        
    try:
        minutes = int(action)
    except ValueError:
        return await query.answer("Invalid Selection", show_alert=True)
        
    # Re-verify that music is active
    if not await is_music_playing(chat_id):
        clean_err = _["sleep_6"].replace("<blockquote>", "").replace("</blockquote>", "").replace("<b>", "").replace("</b>", "").replace("»", "").strip()
        return await query.answer(clean_err, show_alert=True)
        
    # Cancel any active timer task
    if chat_id in timer:
        timer[chat_id].cancel()
        
    async def sleep_timer_handler(chat_id, minutes, lang_code):
        try:
            await asyncio.sleep(minutes * 60)
            if await is_music_playing(chat_id):
                await music_off(chat_id)
                await core_call.Signal.pause_stream(chat_id, is_auto=True)
                
                _inner = get_string(lang_code)
                buttons = [
                    [
                        InlineKeyboardButton(
                            text=_inner["sleep_5"],
                            callback_data=f"ADMIN Resume|{chat_id}"
                        )
                    ]
                ]
                await app.send_message(
                    chat_id,
                    text=_inner["sleep_4"],
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
        except asyncio.CancelledError:
            pass
        finally:
            if chat_id in timer:
                del timer[chat_id]
            sleep_timer_val[chat_id] = 0
            
    timer[chat_id] = asyncio.create_task(sleep_timer_handler(chat_id, minutes, language))
    sleep_timer_val[chat_id] = minutes
    
    clean_ok = _["sleep_3"].format(minutes).replace("<blockquote>", "").replace("</blockquote>", "").replace("<b>", "").replace("</b>", "").replace("»", "").strip()
    await query.answer(clean_ok, show_alert=True)
    
    # Smoothly update the panel interface
    try:
        await query.message.edit_text(
            f"<blockquote><b>🕒 sʟᴇᴇᴘ ᴛɪᴍᴇʀ ᴘᴀɴᴇʟ</b>\n\n» sʟᴇᴇᴘ ᴛɪᴍᴇʀ sᴇᴛ ғᴏʀ <b>{minutes} ᴍɪɴᴜᴛᴇs</b>.\nᴛʜᴇ sᴛʀᴇᴀᴍ ᴡɪʟʟ ᴘᴀᴜsᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ.</blockquote>",
            reply_markup=sleep_timer_markup(minutes)
        )
    except:
        pass
        
    # Check assistant permissions
    try:
        assistant_num = await group_assistant(core_call.Signal, chat_id)
        assistant_client = await get_client(assistant_num)
        assistant_member = await assistant_client.get_chat_member(chat_id, "me")
        if assistant_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await query.message.reply_text(_["sleep_7"].format(assistant_num))
    except:
        pass
