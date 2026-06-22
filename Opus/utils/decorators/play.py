import asyncio
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    ChatWriteForbidden,
    UserAlreadyParticipant,
    UserNotParticipant,
    ChannelsTooMuch,
    RPCError,
    InviteHashExpired,
    ChannelInvalid,
    YouBlockedUser,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Opus import YouTube, app
from Opus.misc import SUDOERS
from Opus.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from Opus.utils.inline import botplaylist_markup
from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string

links = {}

CMD_DELETE = False
CMD_DELETE_DELAY = 86400


async def safe_reply(msg, text, markup=None, **kwargs):
    try:
        return await msg.reply_text(text, reply_markup=markup, **kwargs)
    except ChatWriteForbidden:
        pass
    except Exception:
        pass


async def safe_reply_photo(msg, photo, caption, buttons=None):
    try:
        return await msg.reply_photo(
            photo=photo,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )
    except ChatWriteForbidden:
        pass
    except Exception:
        pass


async def safe_delete_message(msg, delay: int = 0):
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass


def PlayWrapper(command):
    async def wrapper(client, message):
        from pyrogram.types import CallbackQuery
        if isinstance(message, CallbackQuery):
            m = message.message
            m.from_user = message.from_user # Keep the user who clicked the button
        else:
            m = message

        try:
            language = await get_lang(m.chat.id)
            strings = get_string(language)

            if m.sender_chat:
                upl = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("How To Fix ?", callback_data="SignalmousAdmin")]]
                )
                return await safe_reply(message, strings["general_3"], upl)

            if await is_maintenance() is False and m.from_user.id not in SUDOERS:
                return await safe_reply(
                    m,
                    text=f"{app.mention} ɪs uɴᴅᴇʀ ᴍaɪɴᴛᴇɴᴀɴᴄᴇ.\nPlease visit <a href={SUPPORT_CHAT}>support chat for latest updates & discussions</a>.",
                    disable_web_page_preview=True,
                )

            if CMD_DELETE:
                asyncio.create_task(safe_delete_message(m, CMD_DELETE_DELAY))

            audio = (
                m.reply_to_message.audio or m.reply_to_message.voice
            ) if m.reply_to_message else None
            video = (
                m.reply_to_message.video or m.reply_to_message.document
            ) if m.reply_to_message else None
            url = await YouTube.url(m)

            if not (audio or video or url):
                if m.command and len(m.command) < 2:
                    if "stream" in m.command:
                        return await safe_reply(m, strings["str_1"])
                    buttons = botplaylist_markup(strings)
                    return await safe_reply_photo(
                        m, PLAYLIST_IMG_URL, strings["play_18"], buttons
                    )

            if m.command and m.command[0][0] == "c":
                chat_id = await get_cmode(m.chat.id)
                if not chat_id:
                    return await safe_reply(m, strings["setting_7"])
                try:
                    chat = await app.get_chat(chat_id)
                    channel = chat.title
                except Exception:
                    return await safe_reply(m, strings["cplay_4"])
            else:
                chat_id = m.chat.id
                channel = None

            playmode = await get_playmode(m.chat.id)
            playty = await get_playtype(m.chat.id)

            if playty != "Everyone" and m.from_user.id not in SUDOERS:
                admins = adminlist.get(m.chat.id)
                if not admins or m.from_user.id not in admins:
                    return await safe_reply(m, strings["play_4"])

            cmd = (m.command[0] if m.command else "").lstrip("/.!").lower()
            video_cmds = {"vplay", "cvplay", "vplayforce", "cvplayforce"}
            force_cmds = {"playforce", "vplayforce", "cplayforce", "cvplayforce"}
            is_video = True if (cmd in video_cmds or "-v" in (m.text or "").lower()) else None
            fplay = True if cmd in force_cmds else None

            try:
                bot_member = await app.get_chat_member(chat_id, (await app.get_me()).id)
                if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
                    return await safe_reply(
                        m,
                        "ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴍᴏᴛᴇ ꜱᴛᴏʀᴍ ᴍᴜꜱɪᴄ ᴡɪᴛʜ ᴘʀᴏᴘᴇʀ ᴀᴅᴍɪɴ ʀɪɢʜᴛꜱ ᴛᴏ ꜱᴛᴀʀᴛ ꜱᴛʀᴇᴀᴍɪɴɢ 🎵.",
                    )
            except ChatAdminRequired:
                pass
            except Exception:
                pass

            async def get_invite_link(force_new=False):
                invite_link = None
                if not force_new:
                    invite_link = links.get(chat_id)

                if not invite_link:
                    if m.chat.username:
                        invite_link = m.chat.username
                    else:
                        try:
                            invite_link = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            await safe_reply(m, strings["call_1"])
                            return None
                        except Exception as e:
                            await safe_reply(
                                m,
                                strings["call_3"].format(app.mention, type(e).__name__),
                            )
                            return None

                if isinstance(invite_link, str) and invite_link.startswith("https://t.me/+"):
                    invite_link = invite_link.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )

                links[chat_id] = invite_link
                return invite_link

            if not await is_active_chat(chat_id):
                userbot = await get_assistant(chat_id)

                try:
                    member = await app.get_chat_member(chat_id, userbot.id)
                    if member.status in [
                        ChatMemberStatus.BANNED,
                        ChatMemberStatus.RESTRICTED,
                    ]:
                        return await safe_reply(
                            m,
                            strings["call_2"].format(
                                app.mention, userbot.id, userbot.name, userbot.username
                            ),
                        )
                except ChatAdminRequired:
                    return await safe_reply(
                        m,
                        "🛑 Storm Music must have admin rights to check assistant's membership status.",
                    )
                except UserNotParticipant:
                    invite_link = await get_invite_link(False)
                    if not invite_link:
                        return

                    msg = await safe_reply(m, strings["call_4"].format(app.mention))

                    joined = False
                    for attempt in range(2):
                        try:
                            await userbot.join_chat(invite_link)
                            joined = True
                            break
                        except InviteRequestSent:
                            try:
                                await app.approve_chat_join_request(chat_id, userbot.id)
                            except Exception as e:
                                return await safe_reply(
                                    m,
                                    strings["call_3"].format(app.mention, type(e).__name__),
                                )
                            await asyncio.sleep(1)
                            joined = True
                            break
                        except UserAlreadyParticipant:
                            joined = True
                            break
                        except ChannelsTooMuch:
                            note = (
                                "<b>Too many joined groups/channels</b>\n"
                                "🧹 Please run /cleanassistants to clean."
                            )
                            for sudo_id in SUDOERS:
                                try:
                                    await app.send_message(sudo_id, note)
                                except Exception:
                                    pass
                            return await safe_reply(
                                m,
                                "🚫 Assistant has joined too many chats.",
                            )
                        except YouBlockedUser:
                            return await safe_reply(
                                m,
                                strings["call_3"].format(app.mention, "Blocked"),
                            )
                        except (InviteHashExpired, ChannelInvalid):
                            links.pop(chat_id, None)
                            if attempt == 0:
                                invite_link = await get_invite_link(True)
                                if not invite_link:
                                    return
                                continue
                            return await safe_reply(
                                m,
                                strings["call_3"].format(app.mention, "InviteErr"),
                            )
                        except ChatAdminRequired:
                            return await safe_reply(m, strings["call_1"])
                        except RPCError as e:
                            s = str(e)
                            if ("INVITE_HASH_EXPIRED" in s) or ("CHANNEL_INVALID" in s):
                                links.pop(chat_id, None)
                                if attempt == 0:
                                    invite_link = await get_invite_link(True)
                                    if not invite_link:
                                        return
                                    continue
                                return await safe_reply(
                                    m,
                                    strings["call_3"].format(app.mention, "InviteErr"),
                                )
                            if "YOU_BLOCKED_USER" in s:
                                return await safe_reply(
                                    m,
                                    strings["call_3"].format(app.mention, "Blocked"),
                                )
                            return await safe_reply(
                                m,
                                strings["call_3"].format(app.mention, type(e).__name__),
                            )
                        except Exception as e:
                            return await safe_reply(
                                m,
                                strings["call_3"].format(app.mention, type(e).__name__),
                            )

                    if joined:
                        try:
                            await msg.edit_text(strings["call_5"].format(app.mention))
                        except Exception:
                            try:
                                await safe_reply(m, strings["call_5"].format(app.mention))
                            except Exception:
                                pass

            return await command(
                client,
                message, # Pass original message/callback
                strings,
                chat_id,
                is_video,
                channel,
                playmode,
                url,
                fplay,
            )

        except Exception as ex:
            import traceback
            traceback.print_exc()
            error_message = f"🚫 <b>Unexpected Error:</b>\n<pre>{str(ex)}</pre>"
            await safe_reply(message, error_message, disable_web_page_preview=True)
    return wrapper
