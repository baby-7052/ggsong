import asyncio
from Opus.misc import SUDOERS
from Opus.core.userbot import Userbot
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant
from Opus import app
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from Opus import app
from Opus.utils.odatabase import admin_filter
from Opus.utils.decorators.userbotjoin import UserbotWrapper
from Opus.utils.database import get_assistant, is_active_chat

links = {}


@app.on_message(
    filters.group
    & filters.command(["userbotjoin", f"userbotjoin@{app.username}"])
    & ~filters.private
)
async def join_group(client, message):
    chat_id = message.chat.id
    userbot = await get_assistant(message.chat.id)
    userbot_id = userbot.id
    done = await message.reply("ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ɪɴᴠɪᴛɪɴɢ ᴀssɪsᴛᴀɴᴛ")
    await asyncio.sleep(1)
    # Get chat member object
    chat_member = await app.get_chat_member(chat_id, app.id)

    # Condition 1: Group username is present, bot is not admin
    if (
        message.chat.username
        and not chat_member.status == ChatMemberStatus.ADMINISTRATOR
    ):
        try:
            await userbot.join_chat(message.chat.username)
            await done.edit_text("✅ ᴀssɪsᴛᴀɴᴛ ᴊᴏɪɴᴇᴅ.")

        except InviteRequestSent:
            try:
                await app.approve_chat_join_request(chat_id, userbot_id)
            except Exception:
                pass
        except Exception as e:
            await done.edit_text("ɪ ɴᴇᴇᴅ ᴀᴅᴍɪɴ ᴘᴏᴡᴇʀ ᴛᴏ ɪɴᴠɪᴛᴇ ᴍʏ ᴀssɪsᴛᴀɴᴛ!")

    # Condition 2: Group username is present, bot is admin, and Userbot is not banned
    if message.chat.username and chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        try:
            await userbot.join_chat(message.chat.username)
            await done.edit_text("✅ ᴀssɪsᴛᴀɴᴛ ᴊᴏɪɴᴇᴅ.")
        except InviteRequestSent:
            try:
                await app.approve_chat_join_request(chat_id, userbot_id)
            except Exception:
                pass
        except Exception as e:
            await done.edit_text(str(e))

    # Condition 3: Group username is not present/group is private, bot is admin and Userbot is banned
    if message.chat.username and chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        userbot_member = await app.get_chat_member(chat_id, userbot.id)
        if userbot_member.status in [
            ChatMemberStatus.BANNED,
            ChatMemberStatus.RESTRICTED,
        ]:
            try:
                await app.unban_chat_member(chat_id, userbot.id)
                await done.edit_text("ᴀssɪsᴛᴀɴᴛ ɪs ᴜɴʙᴀɴɴɪɴɢ")
                await userbot.join_chat(message.chat.username)
                await done.edit_text(
                    "ᴀꜱꜱɪꜱᴛᴀɴᴛ ᴡᴀꜱ ᴜɴʙᴀɴɴᴇᴅ ᴀɴᴅ ʀᴇᴊᴏɪɴᴇᴅ ✅"
                )
            except InviteRequestSent:
                try:
                    await app.approve_chat_join_request(chat_id, userbot_id)
                except Exception:
                    pass
            except Exception as e:
                await done.edit_text(
                    "ғᴀɪʟᴇᴅ ᴛᴏ ᴊᴏɪɴ, ᴘʟᴇᴀsᴇ ɢɪᴠᴇ [ʙᴀɴ ᴘᴏᴡᴇʀ ᴀɴᴅ ɪɴᴠɪᴛᴇ ᴜsᴇʀ] ᴘᴏᴡᴇʀ ᴏʀ ᴜɴʙᴀɴ ᴀssɪsᴛᴀɴᴛ ᴍᴀɴᴜᴀʟʟʏ ᴛʜᴇɴ ᴛʀʏ ᴀɢᴀɪɴ"
                )
        return

    # Condition 4: Group username is not present/group is private, bot is not admin
    if (
        not message.chat.username
        and not chat_member.status == ChatMemberStatus.ADMINISTRATOR
    ):
        await done.edit_text("ɪ ɴᴇᴇᴅ ᴀᴅᴍɪɴ ᴘᴏᴡᴇʀ ᴛᴏ ɪɴᴠɪᴛᴇ ᴍʏ ᴀssɪsᴛᴀɴᴛ.")

    # Condition 5: Group username is not present/group is private, bot is admin
    if (
        not message.chat.username
        and chat_member.status == ChatMemberStatus.ADMINISTRATOR
    ):
        try:
            try:
                userbot_member = await app.get_chat_member(chat_id, userbot.id)
                if userbot_member.status not in [
                    ChatMemberStatus.BANNED,
                    ChatMemberStatus.RESTRICTED,
                ]:
                    await done.edit_text("✅ ᴀssɪsᴛᴀɴᴛ ᴀʟʀᴇᴀᴅʏ ᴊᴏɪɴᴇᴅ.")
                    return
            except Exception as e:
                await done.edit_text("ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ɪɴᴠɪᴛɪɴɢ ᴀssɪsᴛᴀɴᴛ")
                await done.edit_text("ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ɪɴᴠɪᴛɪɴɢ ᴀssɪsᴛᴀɴᴛ")
                invite_link = await app.create_chat_invite_link(
                    chat_id, expire_date=None
                )
                await asyncio.sleep(2)
                await userbot.join_chat(invite_link.invite_link)
                await done.edit_text("✅ ᴀssɪsᴛᴀɴᴛ ᴊᴏɪɴᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ.")
        except InviteRequestSent:
            try:
                await app.approve_chat_join_request(chat_id, userbot_id)
            except Exception:
                pass
        except Exception as e:
            await done.edit_text(
                f"[Ɵᴘᴜs] ғᴏᴜɴᴅ ᴛʜᴀᴛ ᴍʏ ᴀssɪsᴛᴀɴᴛ ʜᴀs ɴᴏᴛ ᴊᴏɪɴ ᴛʜɪs ɢʀᴏᴜᴘ ᴀɴᴅ ɪ ᴀᴍ ɴᴏᴛ ᴀʙʟᴇ ᴛᴏ ɪɴᴠɪᴛᴇ ᴍʏ ᴀssɪsᴛᴀɴᴛ ʙᴇᴄᴀᴜsᴇ [ ɪ ᴅᴏɴᴛ ʜᴀᴠᴇ  ɪɴᴠɪᴛᴇ ᴜsᴇʀ ᴀᴅᴍɪɴ ᴘᴏᴡᴇʀ ] sᴏ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴍᴇ ɪɴᴠɪᴛᴇ ᴜsᴇʀs ᴀᴅᴍɪɴ ᴘᴏᴡᴇʀ ᴛʜᴇɴ ᴛʀʏ ᴀɢᴀɪɴ"
            )

    # Condition 6: Group username is not present/group is private, bot is admin and Userbot is banned
    if (
        not message.chat.username
        and chat_member.status == ChatMemberStatus.ADMINISTRATOR
    ):
        userbot_member = await app.get_chat_member(chat_id, userbot.id)
        if userbot_member.status in [
            ChatMemberStatus.BANNED,
            ChatMemberStatus.RESTRICTED,
        ]:
            try:
                await app.unban_chat_member(chat_id, userbot.id)
                await done.edit_text(
                    "ᴀssɪsᴛᴀɴᴛ ɪs ᴜɴʙᴀɴɴᴇᴅ"
                )
                invite_link = await app.create_chat_invite_link(
                    chat_id, expire_date=None
                )
                await asyncio.sleep(2)
                await userbot.join_chat(invite_link.invite_link)
                await done.edit_text(
                    "ᴀꜱꜱɪꜱᴛᴀɴᴛ ᴡᴀꜱ ᴜɴʙᴀɴɴᴇᴅ ᴀɴᴅ ʀᴇᴊᴏɪɴᴇᴅ ✅"
                )
            except InviteRequestSent:
                try:
                    await app.approve_chat_join_request(chat_id, userbot_id)
                except Exception:
                    pass

            except Exception as e:
                await done.edit_text(
                    f"[vx] ғᴏᴜɴᴅ ᴛʜᴀᴛ ᴍʏ ᴀssɪsᴛᴀɴᴛ ʜᴀs ɴᴏᴛ ᴊᴏɪɴ ᴛʜɪs ɢʀᴏᴜᴘ ᴀɴᴅ ɪ ᴀᴍ ɴᴏᴛ ᴀʙʟᴇ ᴛᴏ ɪɴᴠɪᴛᴇ ᴍʏ ᴀssɪsᴛᴀɴᴛ ʙᴇᴄᴀᴜsᴇ [ ɪ ᴅᴏɴᴛ ʜᴀᴠᴇ  ɪɴᴠɪᴛᴇ ᴜsᴇʀ ᴀᴅᴍɪɴ ᴘᴏᴡᴇʀ ] sᴏ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴍᴇ ɪɴᴠɪᴛᴇ ᴜsᴇʀs ᴀᴅᴍɪɴ ᴘᴏᴡᴇʀ ᴛʜᴇɴ ᴛʀʏ ᴀɢᴀɪɴ"
                )
        return