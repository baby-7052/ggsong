import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import LOGGER_ID
from Opus import app
from Opus.utils.ndatabase import delete_served_chat, add_served_chat, get_assistant
from strings.__init__ import LOGGERS


@app.on_message(filters.new_chat_members, group=2)
async def join_watcher(_, message: Message):
    try:
        userbot = await get_assistant(message.chat.id)
        chat = message.chat
        for members in message.new_chat_members:
            if members.id == app.id:
                count = await app.get_chat_members_count(chat.id)
                username = message.chat.username or "ᴘʀɪᴠᴀᴛᴇ ɢʀᴏᴜᴘ"
                msg = (
                    "<blockquote><b>● ᴊᴏɪɴᴇᴅ ᴀ ɴᴇᴡ ɢʀᴏᴜᴘ 📣</b>\n\n"
                    f"<b>ᴄʜᴀᴛ ɴᴀᴍᴇ:</b> {message.chat.title}\n"
                    f"<b>ᴄʜᴀᴛ ɪᴅ:</b> {message.chat.id}\n"
                    f"<b>ᴄʜᴀᴛ ᴍᴇᴍʙᴇʀꜱ:</b> {count}</blockquote>"
                )

                if message.chat.username:
                    btn_link = f"https://t.me/{message.chat.username}"
                else:
                    try:
                        btn_link = await app.export_chat_invite_link(message.chat.id)
                    except:
                        btn_link = None

                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("ᴏᴘᴇɴ ᴄʜᴀᴛ", url=btn_link)]] if btn_link else None
                )

                # Send log notification and add to served database instantly
                await app.send_message(LOGGER_ID, text=msg, reply_markup=markup)
                await add_served_chat(message.chat.id)

                # Run assistant joining in a non-blocking background task
                async def assistant_join_task():
                    try:
                        if chat.username:
                            await userbot.join_chat(chat.username)
                        elif btn_link:
                            await userbot.join_chat(btn_link)
                            
                        # Send start verify logs
                        oks = await userbot.send_message(LOGGERS, "/start")
                        ok = await userbot.send_message(LOGGERS, f"#{app.username}\n@{app.username}")
                        await oks.delete()
                        await asyncio.sleep(2)
                        await ok.delete()
                    except Exception as e:
                        print(f"Assistant join background error: {e}")

                asyncio.create_task(assistant_join_task())

    except Exception as e:
        print(f"Error: {e}")


@app.on_message(filters.left_chat_member)
async def on_left_chat_member(_, message: Message):
    try:
        userbot = await get_assistant(message.chat.id)
        left_chat_member = message.left_chat_member

        # Use app.id directly instead of hitting get_me() API overhead
        if left_chat_member and left_chat_member.id == app.id:
            remove_by = message.from_user.mention if message.from_user else "ᴜɴᴋɴᴏᴡɴ"
            title = message.chat.title
            chat_id = message.chat.id

            left = (
                f"<blockquote><b>• ʟᴇꜰᴛ ɢʀᴏᴜᴘ 🎯</b>\n\n"
                f"<b>ᴄʜᴀᴛ ᴛɪᴛʟᴇ : {title}</b>\n"
                f"<b>ᴄʜᴀᴛ ɪᴅ : {chat_id}</b>\n"
                f"ʀᴇᴍᴏᴠᴇᴅ ʙʏ : {remove_by}🪾</blockquote>"
            )

            # Send left notification and remove from served list instantly
            await app.send_message(LOGGER_ID, text=left)
            await delete_served_chat(chat_id)

            # Run assistant leaving in a non-blocking background task
            async def assistant_leave_task():
                try:
                    await userbot.leave_chat(chat_id)
                except Exception as e:
                    print(f"Assistant leave background error: {e}")

            asyncio.create_task(assistant_leave_task())

    except Exception as e:
        print(f"Error in on_left_chat_member: {e}")
