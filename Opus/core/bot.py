import os
import sys
from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus, ParseMode
import asyncio
import time

import config
from ..logging import LOGGER

from pyrogram import types


try:
    _old_story_parse = types.Story._parse
    async def _new_story_parse(*args, **kwargs):
        try:
            return await _old_story_parse(*args, **kwargs)
        except errors.PeerIdInvalid:
            return None
        except Exception:
            return None

    types.Story._parse = _new_story_parse
except AttributeError:
    LOGGER(__name__).warning("Pyrogram.types has no attribute 'Story'. Skipping story patch.")


class Signal(Client):
    def __init__(self):
        super().__init__(
            name="OpusMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            max_concurrent_transmissions=7,
            parse_mode=ParseMode.HTML,
        )
        LOGGER(__name__).info("[bold cyan]● SYSTEM[/bold cyan] | Aurex core engines initialized.")

    async def start(self):
        await super().start()

        me = await self.get_me()
        self.username, self.id = me.username, me.id
        self.name = f"{me.first_name} {me.last_name or ''}".strip()
        self.mention = me.mention

        try:
            await self.send_message(
                config.LOGGER_ID,
                (
                    f"<b>Oᴘᴜs Bᴏᴛ ɪs ʀᴇᴀᴅʏ ᴛᴏ ᴠɪʙᴇ ᴏɴ 🍁</b>\n\n"
                    f"• ɴᴀᴍᴇ : {self.name}\n"
                    f"• ᴜsᴇʀɴᴀᴍᴇ : @{self.username}\n"
                    f"• ɪᴅ : <code>{self.id}</code>"
                ),
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error(
                "🚫 Lᴏɢɢᴇʀ ᴄʜᴀᴛ ɴᴏᴛ ᴀᴄᴄᴇssɪʙʟᴇ. ᴀᴅᴅ Bᴏᴛ ᴛʜᴇʀᴇ & ᴘʀᴏᴍᴏᴛᴇ ɪᴛ ғɪʀsᴛ."
            )
            sys.exit()
        except Exception as exc:
            LOGGER(__name__).error(
                f"❌ Fᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ sᴛᴀʀᴛᴜᴘ ɴᴏᴛɪғɪᴄᴀᴛɪᴏɴ: {type(exc).__name__}"
            )
            sys.exit()

        try:
            member = await self.get_chat_member(config.LOGGER_ID, self.id)
            if member.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error(
                    "⚠️ Bᴏᴛ ᴍᴜsᴛ ʙᴇ ᴀᴅᴍɪɴ ɪɴ ʟᴏɢɢᴇʀ ᴄʜᴀᴛ ᴛᴏ sᴇɴᴅ ʀᴇᴘᴏʀᴛs."
                )
                sys.exit()
        except Exception as e:
            LOGGER(__name__).error(
                f"❌ Eʀʀᴏʀ ᴄʜᴇᴄᴋɪɴɢ ᴀᴅᴍɪɴ sᴛᴀᴛᴜs: {e}"
            )
            sys.exit()

        LOGGER(__name__).info(f"[bold cyan]● CLIENT[/bold cyan] | Bot online as [bold underline]{self.name}[/bold underline] (@{self.username})")
