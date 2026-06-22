import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from Opus import LOGGER, app, userbot
from Opus.core.call import Signal
from Opus.misc import sudo
from Opus.plugins import ALL_MODULES
from Opus.utils.database import get_banned_users, get_gbanned, init_database_indexes
from config import BANNED_USERS

async def init():
    import os
    from datetime import datetime
    
    os.makedirs("logs", exist_ok=True)
    
    for log_file in ["logs/api.txt", "logs/log.txt", "logs/bot.log", "logs/reboot.txt"]:
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"--- Bot Restarted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        except Exception:
            pass
            
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("⚠️ Aᴄᴛɪᴠᴀᴛɪᴏɴ Fᴀɪʟᴇᴅ » Assɪsᴛᴀɴᴛ sᴇssɪᴏɴs ᴀʀᴇ ᴍɪssɪɴɢ.")
        exit()
    await sudo()
    try:
        await init_database_indexes()
    except Exception as e:
        LOGGER("Opus").warning(f"⚠️ Index initialization skipped: {e}")
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("Opus.plugins" + all_module)
    LOGGER("Opus.plugins").info("[bold cyan]● SYSTEM[/bold cyan] | Constellation modules successfully synchronized.")
    await userbot.start()
    await Signal.start()
    try:
        await Signal.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("Opus").error(
            "🔇 Nᴏ Aᴄᴛɪᴠᴇ VC » Lᴏɢ Gʀᴏᴜᴘ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ɪs ᴅᴏʀᴍᴀɴᴛ.\n💀 Aʙᴏʀᴛɪɴɢ Oᴘᴜs Lᴀᴜɴᴄʜ..."
        )
        exit()
    except:
        pass
    await Signal.decorators()
    # Smart Resume: Restore previous sessions
    await Signal.startup_resume()
    LOGGER("Opus").info("[bold cyan]● AURORA[/bold cyan] | Storm sequence fully active and synchronized.")
    
    # Start Dummy Web Server for Render
    from aiohttp import web
    import os
    async def web_server():
        async def handle(request):
            return web.Response(text="Bot is running")
        web_app = web.Application()
        web_app.router.add_get('/', handle)
        runner = web.AppRunner(web_app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        LOGGER("Opus").info(f"Dummy web server started on port {port}")
    await web_server()

    await idle()
    await Signal.stop()
    await app.stop()
    await userbot.stop()
    LOGGER("Opus").info("[bold red]● SYSTEM[/bold red] | Core engines terminated. All drivers offline.")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
