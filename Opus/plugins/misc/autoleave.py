import asyncio
from datetime import datetime

from pyrogram.enums import ChatType

import config
from Opus import app
from Opus.core.call import Signal, autoend
from Opus.utils.database import active, get_client, is_active_chat, is_autoend


async def auto_leave():
    if config.AUTO_LEAVING_ASSISTANT:
        while not await asyncio.sleep(86400):
            from Opus.core.userbot import assistants

            for num in assistants:
                client = await get_client(num)
                left = 0
                try:
                    async for i in client.get_dialogs():
                        if i.chat.type in [
                            ChatType.SUPERGROUP,
                            ChatType.GROUP,
                            ChatType.CHANNEL,
                        ]:
                            if (
                                i.chat.id != config.LOGGER_ID
                                and i.chat.id != --1002030443562
                                and i.chat.id != -1002064111110
                            ):
                                if left == 20:
                                    continue
                                if not await is_active_chat(i.chat.id):
                                    try:
                                        await client.leave_chat(i.chat.id)
                                        left += 1
                                    except:
                                        continue
                except:
                    pass


asyncio.create_task(auto_leave())


async def auto_end():
    while not await asyncio.sleep(5):
        for chat_id in list(active):
            await Signal.check_autoend(chat_id)


asyncio.create_task(auto_end())
