import asyncio
import os
import shutil
import socket
from datetime import datetime

import urllib3
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from pyrogram import filters

import config
from Opus import app
from Opus.misc import HAPP, SUDOERS, XCB
from Opus.utils.database import (
    get_active_chats,
    remove_active_chat,
    remove_active_video_chat,
)
from Opus.utils.decorators.language import language
from Opus.utils.pastebin import SignalBin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


async def is_heroku():
    return "heroku" in socket.getfqdn()


@app.on_message(filters.command(["getlog", "logs", "getlogs"]) & SUDOERS)
@language
async def log_(client, message, _):
    try:
        await message.reply_document(document="log.txt")
    except:
        await message.reply_text(_["server_1"])


@app.on_message(filters.command(["rebootlog", "smartlog"]) & SUDOERS)
@language
async def reboot_log_cmd(client, message, _):
    try:
        if os.path.exists("reboot.txt"):
            await message.reply_document(document="reboot.txt", caption="✨ **Smart Resume & Reboot History**")
        else:
            await message.reply_text("ɴᴏ ʀᴇʙᴏᴏᴛ ʟᴏɢs ғᴏᴜɴᴅ ʏᴇᴛ.")
    except Exception as e:
        await message.reply_text(f"ғᴀɪʟᴇᴅ ᴛᴏ ɢᴇᴛ ʀᴇʙᴏᴏᴛ ʟᴏɢs.\n\nᴇʀʀᴏʀ: {e}")


@app.on_message(filters.command(["update", "gitpull"]) & SUDOERS)
@language
async def update_(client, message, _):
    if await is_heroku():
        if HAPP is None:
            return await message.reply_text(_["server_2"])
    response = await message.reply_text(_["server_3"])
    try:
        from Opus.core.call import _reboot_log
        await _reboot_log(f"CMD: Update/Restart triggered by {message.from_user.first_name} ({message.from_user.id})")
    except:
        pass
    try:

        repo = Repo()
    except GitCommandError:
        return await response.edit(_["server_4"])
    except InvalidGitRepositoryError:
        return await response.edit(_["server_5"])
    to_exc = f"git fetch origin {config.UPSTREAM_BRANCH} &> /dev/null"
    os.system(to_exc)
    await asyncio.sleep(7)
    verification = ""
    REPO_ = repo.remotes.origin.url.split(".git")[0]
    for checks in repo.iter_commits(f"HEAD..origin/{config.UPSTREAM_BRANCH}"):
        verification = str(checks.count())
    if verification == "":
        return await response.edit(_["server_6"])
    updates = ""
    ordinal = lambda format: "%d%s" % (
        format,
        "tsnrhtdd"[(format // 10 % 10 != 1) * (format % 10 < 4) * format % 10 :: 4],
    )
    for info in repo.iter_commits(f"HEAD..origin/{config.UPSTREAM_BRANCH}"):
        updates += f"<b>➣ #{info.count()}: <a href={REPO_}/commit/{info}>{info.summary}</a> ʙʏ -> {info.author}</b>\n\t\t\t\t<b>➥ ᴄᴏᴍᴍɪᴛᴇᴅ ᴏɴ :</b> {ordinal(int(datetime.fromtimestamp(info.committed_date).strftime('%d')))} {datetime.fromtimestamp(info.committed_date).strftime('%b')}, {datetime.fromtimestamp(info.committed_date).strftime('%Y')}\n\n"
    _update_response_ = "<b>ᴀ ɴᴇᴡ ᴜᴩᴅᴀᴛᴇ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜᴇ ʙᴏᴛ !</b>\n\n➣ ᴩᴜsʜɪɴɢ ᴜᴩᴅᴀᴛᴇs ɴᴏᴡ\n\n<b><u>ᴜᴩᴅᴀᴛᴇs:</u></b>\n\n"
    _final_updates_ = _update_response_ + updates
    if len(_final_updates_) > 4096:
        url = await SignalBin(updates)
        nrs = await response.edit(
            f"<b>ᴀ ɴᴇᴡ ᴜᴩᴅᴀᴛᴇ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜᴇ ʙᴏᴛ !</b>\n\n➣ ᴩᴜsʜɪɴɢ ᴜᴩᴅᴀᴛᴇs ɴᴏᴡ\n\n<u><b>ᴜᴩᴅᴀᴛᴇs :</b></u>\n\n<a href={url}>ᴄʜᴇᴄᴋ ᴜᴩᴅᴀᴛᴇs</a>"
        )
    else:
        nrs = await response.edit(_final_updates_, disable_web_page_preview=True)
    os.system("git stash &> /dev/null && git pull")

    try:
        served_chats = await get_active_chats()
        for x in served_chats:
            try:
                await app.send_message(
                    chat_id=int(x),
                    text=_["server_8"].format(app.mention),
                )
                await remove_active_chat(x)
                await remove_active_video_chat(x)
            except:
                pass
        await response.edit(f"{nrs.text}\n\n{_['server_7']}")
    except:
        pass

    if await is_heroku():
        try:
            os.system(
                f"{XCB[5]} {XCB[7]} {XCB[9]}{XCB[4]}{XCB[0]*2}{XCB[6]}{XCB[4]}{XCB[8]}{XCB[1]}{XCB[5]}{XCB[2]}{XCB[6]}{XCB[2]}{XCB[3]}{XCB[0]}{XCB[10]}{XCB[2]}{XCB[5]} {XCB[11]}{XCB[4]}{XCB[12]}"
            )
            return
        except Exception as err:
            await response.edit(f"{nrs.text}\n\n{_['server_9']}")
            return await app.send_message(
                chat_id=config.LOGGER_ID,
                text=_["server_10"].format(err),
            )
    else:
        os.system("pip3 install -r requirements.txt")
        # Flush all active queue states to MongoDB BEFORE killing
        try:
            from Opus.core.call import Signal as _Signal
            await _Signal.stop()
        except:
            pass
        os.system(f"kill -9 {os.getpid()} && bash start")
        exit()


@app.on_message(filters.command(["restart"]) & SUDOERS)
async def restart_(_, message):
    response = await message.reply_text("ʀᴇsᴛᴀʀᴛɪɴɢ...")
    try:
        from Opus.core.call import _reboot_log
        await _reboot_log(f"CMD: Manual Restart triggered by {message.from_user.first_name} ({message.from_user.id})")
    except:
        pass
    ac_chats = await get_active_chats()

    for x in ac_chats:
        try:
            await app.send_message(
                chat_id=int(x),
                text=f"<blockquote>🔄 <b>sᴍᴀʀᴛ ʀᴇsᴛᴀʀᴛ ɪɴ ᴘʀᴏɢʀᴇss...</b></blockquote>\n<blockquote><i>ʏᴏᴜʀ ᴍᴜsɪᴄ ᴡɪʟʟ ʀᴇsᴜᴍᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ғʀᴏᴍ ᴡʜᴇʀᴇ ɪᴛ sᴛᴏᴘᴘᴇᴅ.</i></blockquote>",
            )
        except:
            pass

    # Flush all active queue states to MongoDB BEFORE killing
    try:
        from Opus.core.call import Signal as _Signal
        await _Signal.stop()
    except Exception as e:
        pass

    try:
        shutil.rmtree("downloads")
        shutil.rmtree("raw_files")
        shutil.rmtree("cache")
    except:
        pass
    await response.edit_text(
        "» ʀᴇsᴛᴀʀᴛ ᴘʀᴏᴄᴇss sᴛᴀʀᴛᴇᴅ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ғᴇᴡ sᴇᴄᴏɴᴅs ᴜɴᴛɪʟ ᴛʜᴇ ʙᴏᴛ sᴛᴀʀᴛs..."
    )
    os.system(f"kill -9 {os.getpid()} && bash start")
