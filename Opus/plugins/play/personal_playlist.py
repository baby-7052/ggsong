from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ForceReply
from Opus import app
from Opus.utils.database import get_playlist, add_to_playlist, remove_from_playlist, clear_playlist
from Opus.utils.decorators.play import PlayWrapper
from config import BANNED_USERS
import asyncio
import random

MOVE_PLAYLIST_STATES = {}

# --- HELPER: Extract song info from message ---
def get_song_info(message: Message):
    title = None
    vidid = None
    performer = "Artist"
    
    # Try to find link in message
    if message.caption:
        lines = message.caption.split("\n")
        for line in lines:
            if "•" in line:
                if not title:
                    title = line.replace("•", "").strip()
                else:
                    performer = line.replace("•", "").strip()
                    break
    
    # Extract vidid from button callback if possible
    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for btn in row:
                if btn.callback_data and ("MusicStream" in btn.callback_data or "SpotifyLike" in btn.callback_data or "PlaylistToggle" in btn.callback_data):
                    data = btn.callback_data.split()
                    if len(data) > 1:
                        vidid = data[1].split("|")[0]
                        break
    return title, vidid, performer

# --- CALLBACK: Toggle Playlist (Like/Unlike) ---
@app.on_callback_query(filters.regex(r"^PlaylistToggle"))
async def playlist_toggle_callback(client, callback_query: CallbackQuery):
    data = callback_query.data.split()
    if len(data) < 2:
        return await callback_query.answer("Iɴᴠᴀʟɪᴅ ᴄᴀʟʟʙᴀᴄᴋ. ❌", show_alert=True)
    
    vidid = data[1]
    user_id = callback_query.from_user.id
    from Opus.utils.database import is_on_playlist, add_to_playlist, remove_from_playlist
    
    liked = await is_on_playlist(user_id, vidid)
    if liked:
        await callback_query.answer("Already added!!", show_alert=True)
        return
    else:
        # Add to playlist
        title, _, performer = get_song_info(callback_query.message)
        if not title:
            # Try to get from caption
            if callback_query.message.caption:
                title = callback_query.message.caption.split("\n")[0]
            else:
                title = "Unknown Song"
        
        song_data = {
            "title": title,
            "vidid": vidid,
            "performer": performer,
        }
        added = await add_to_playlist(user_id, song_data)
        if added:
            await callback_query.answer(f"Aᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ!\n\n🎵 {title[:30]}", show_alert=True)
        else:
            await callback_query.answer("Already added!!", show_alert=True)

# --- COMMAND: View Playlist ---
@app.on_message(filters.command(["playlist", "myplaylist"]) & ~BANNED_USERS)
async def view_playlist(client, message: Message):
    user_id = message.from_user.id
    playlist = await get_playlist(user_id)
    
    if not playlist:
        return await message.reply_text("<blockquote><b>ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ ɪs ᴇᴍᴘᴛʏ! 🥀</b>\n\nᴜsᴇ ᴛʜᴇ + ʙᴜᴛᴛᴏɴ ᴏɴ ᴀɴʏ sᴏɴɢ ᴛᴏ ᴀᴅᴅ ɪᴛ ʜᴇʀᴇ.</blockquote>")

    per_page = 5
    total_pages = max(1, (len(playlist) + per_page - 1) // per_page)
    page = 0
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_page_songs = playlist[start_idx:end_idx]

    text = f"<blockquote><b>🎧 ʏᴏᴜʀ ᴘᴇʀsᴏɴᴀʟ ᴘʟᴀʏʟɪsᴛ</b>\n\n<b>• Pᴀɢᴇ :</b> {page+1}/{total_pages}</blockquote>\n\n"
    buttons = []
    
    for song in current_page_songs:
        title = song['title']
        vidid = song['vidid']
        display_name = (title[:25] + "..") if len(title) > 25 else title
        buttons.append([
            InlineKeyboardButton(text=display_name, callback_data=f"MusicStream {vidid}|{user_id}|a|None|0")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="▶️ ᴘʟᴀʏ ᴀʟʟ", callback_data="PlaylistPlayAll"),
        InlineKeyboardButton(text="⚙️ ᴍᴏʀᴇ", callback_data=f"PlaylistMoreMenu {page}")
    ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="<", callback_data=f"PlaylistBack {page-1}"))
    nav_buttons.append(InlineKeyboardButton(text="ᴄʟᴏsᴇ", callback_data="close"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text=">", callback_data=f"PlaylistBack {page+1}"))
    buttons.append(nav_buttons)
    
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^PlaylistBack"))
async def playlist_back_callback(client, callback_query: CallbackQuery):
    data = callback_query.data.split()
    page = int(data[1]) if len(data) > 1 else 0
    
    user_id = callback_query.from_user.id
    playlist = await get_playlist(user_id)
    if not playlist:
        return await callback_query.message.edit_text("<b>ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ ɪs ᴇᴍᴘᴛʏ!</b>")
    
    per_page = 5
    total_pages = max(1, (len(playlist) + per_page - 1) // per_page)
    if page >= total_pages:
        page = max(0, total_pages - 1)
        
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_page_songs = playlist[start_idx:end_idx]
    
    text = f"<blockquote><b>🎧 ʏᴏᴜʀ ᴘᴇʀsᴏɴᴀʟ ᴘʟᴀʏʟɪsᴛ</b>\n\n<b>• Pᴀɢᴇ :</b> {page+1}/{total_pages}</blockquote>\n\n"
    buttons = []
    for song in current_page_songs:
        title = song['title']
        vidid = song['vidid']
        display_name = (title[:25] + "..") if len(title) > 25 else title
        buttons.append([
            InlineKeyboardButton(text=display_name, callback_data=f"MusicStream {vidid}|{user_id}|a|None|0")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="▶️ ᴘʟᴀʏ ᴀʟʟ", callback_data="PlaylistPlayAll"),
        InlineKeyboardButton(text="⚙️ ᴍᴏʀᴇ", callback_data=f"PlaylistMoreMenu {page}")
    ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="<", callback_data=f"PlaylistBack {page-1}"))
    nav_buttons.append(InlineKeyboardButton(text="ᴄʟᴏsᴇ", callback_data="close"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text=">", callback_data=f"PlaylistBack {page+1}"))
    buttons.append(nav_buttons)
    
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^PlaylistMoreMenu"))
async def playlist_more_menu(client, callback_query: CallbackQuery):
    data = callback_query.data.split()
    page = int(data[1]) if len(data) > 1 else 0
    
    text = "<blockquote><b>⚙️ ᴘʟᴀʏʟɪsᴛ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ</b>\n\nCʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ.</blockquote>"
    
    buttons = [
        [
            InlineKeyboardButton(text="🗑️ ʀᴇᴍᴏᴠᴇ ᴇᴀᴄʜ", callback_data=f"PlaylistDelMenu {page}")
        ],
        [
            InlineKeyboardButton(text="🗑️ ʀᴇᴍᴏᴠᴇ ᴀʟʟ", callback_data="PlaylistClear")
        ],
        [
            InlineKeyboardButton(text="📤 ᴍᴏᴠᴇ ᴘʟᴀʏʟɪsᴛ", callback_data="PlaylistMoveReq")
        ],
        [
            InlineKeyboardButton(text="🔙 ʙᴀᴄᴋ", callback_data=f"PlaylistBack {page}"),
            InlineKeyboardButton(text="ᴄʟᴏsᴇ", callback_data="close")
        ]
    ]
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^PlaylistDelMenu"))
async def del_menu_callback(client, callback_query: CallbackQuery):
    data = callback_query.data.split()
    page = int(data[1]) if len(data) > 1 else 0
    user_id = callback_query.from_user.id
    playlist = await get_playlist(user_id)
    
    if not playlist:
        return await callback_query.answer("ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ ɪs ᴇᴍᴘᴛʏ!", show_alert=True)
        
    per_page = 5
    total_pages = max(1, (len(playlist) + per_page - 1) // per_page)
    if page >= total_pages:
        page = max(0, total_pages - 1)
        
    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_page_songs = playlist[start_idx:end_idx]
    
    text = f"<b>🗑️ sᴇʟᴇᴄᴛ ᴀ sᴏɴɢ ᴛᴏ ʀᴇᴍᴏᴠᴇ (Pᴀɢᴇ {page+1}/{total_pages}):</b>\n\n"
    for i, song in enumerate(current_page_songs, start=1):
        title = song['title']
        text += f"<b>{i}.</b> {title[:40]}\n"
        
    buttons = []
    row = []
    for i, song in enumerate(current_page_songs, start=1):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"PlaylistDel {song['vidid']} {page}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="<", callback_data=f"PlaylistDelMenu {page-1}"))
    nav_buttons.append(InlineKeyboardButton(text="ᴄʟᴏsᴇ", callback_data="close"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text=">", callback_data=f"PlaylistDelMenu {page+1}"))
    
    buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton(text="🔙 ʙᴀᴄᴋ", callback_data="PlaylistBack")])
    
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- CALLBACK: Delete from Playlist ---
@app.on_callback_query(filters.regex(r"^PlaylistDel "))
async def del_playlist_callback(client, callback_query: CallbackQuery):
    data = callback_query.data.split()
    vidid = data[1]
    page = int(data[2]) if len(data) > 2 else 0
    user_id = callback_query.from_user.id
    await remove_from_playlist(user_id, vidid)
    await callback_query.answer("Sᴏɴɢ ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ᴘʟᴀʏʟɪsᴛ! 🗑️")
    # Refresh view
    callback_query.data = f"PlaylistDelMenu {page}"
    await del_menu_callback(client, callback_query)

# --- CALLBACK: Clear Playlist ---
@app.on_callback_query(filters.regex(r"^PlaylistClear"))
async def clear_playlist_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    await clear_playlist(user_id)
    await callback_query.answer("ᴘʟᴀʏʟɪsᴛ ᴄʟᴇᴀʀᴇᴅ! 🗑️", show_alert=True)
    await callback_query.message.edit_text("ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ ɪs ɴᴏᴡ ᴇᴍᴘᴛʏ.")

# --- COMMAND/CALLBACK: Play Personal Playlist ---
@app.on_message(filters.command(["playplaylist", "playmine"]) & filters.group & ~BANNED_USERS)
@app.on_callback_query(filters.regex(r"^PlaylistPlayAll"))
@PlayWrapper
async def play_playlist_command(client, message, strings, chat_id, video, channel, playmode, url, fplay):
    user_id = message.from_user.id
    is_callback = isinstance(message, CallbackQuery)
    
    # 1. Handle "MINE" or Button Click (Personal Playlist)
    is_mine = False
    if is_callback:
        is_mine = True
    elif len(message.command) > 1 and message.command[1].lower() == "mine":
        is_mine = True

    if is_mine:
        playlist = await get_playlist(user_id)
        if not playlist:
            if is_callback:
                return await message.answer("ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ ɪs ᴇᴍᴘᴛʏ!", show_alert=True)
            return await message.reply_text("ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ ɪs ᴇᴍᴘᴛʏ!")

        mystic = await (message.edit_message_text if is_callback else message.reply_text)(
            "<b><blockquote>🌀 ᴘʀᴇᴘᴀʀɪɴɢ ʏᴏᴜʀ ᴘᴇʀsᴏɴᴀʟ ᴘʟᴀʏʟɪsᴛ... ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ.</blockquote></b>"
        )

        from Opus.utils.stream.stream import stream
        try:
            return await stream(
                strings, mystic, user_id, playlist, chat_id, message.from_user.first_name, chat_id,
                video=video, streamtype="playlist", forceplay=fplay,
            )
        except Exception as ex:
            import traceback
            traceback.print_exc()
            raise ex

    # 2. Handle Global Search (if query provided or no 'mine' word)
    query = None
    if not is_callback:
        if len(message.command) > 1:
            query = message.text.split(None, 1)[1]
        elif url:
            query = url

    if query:
        from Opus import Vortex
        # Direct URL
        if url and ("spotify.com" in url or "vortex" in url):
            try:
                p_id = url.split("/")[-1].split("?")[0]
                mystic = await message.reply_text("<b><blockquote>🌀 ғᴇᴛᴄʜɪɴɢ ᴘʟᴀʏʟɪsᴛ ᴛʀᴀᴄᴋs... ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ.</blockquote></b>")
                playlist_tracks = await Vortex.get_playlist_details(p_id)
                if not playlist_tracks:
                    return await mystic.edit_text("<b>🚫 ᴇʀʀᴏʀ: ᴜɴᴀʙʟᴇ ᴛᴏ ғᴇᴛᴄʜ ᴛʀᴀᴄᴋs.</b>")

                from Opus.utils.stream.stream import stream
                return await stream(
                    strings, mystic, user_id, playlist_tracks, chat_id,
                    message.from_user.first_name, chat_id, video=video, streamtype="playlist", forceplay=fplay,
                )
            except Exception as e:
                return await message.reply_text(f"<b>🚫 ᴇʀʀᴏʀ:</b> <code>{e}</code>")

        # Search Query
        mystic = await message.reply_text("<b><blockquote>🔍 sᴇᴀʀᴄʜɪɴɢ ғᴏʀ ᴘʟᴀʏʟɪsᴛs...</blockquote></b>")
        try:
            playlists = await Vortex.search_playlists(query)
            if not playlists:
                return await mystic.edit_text("<b>🚫 ɴᴏ ᴘʟᴀʏʟɪsᴛs ғᴏᴜɴᴅ.</b>")

            buttons = []
            for p in playlists[:6]:
                p_name = p.get("title") or p.get("name") or "Unknown Playlist"
                p_id = p.get("id")
                display_name = (p_name[:25] + "..") if len(p_name) > 25 else p_name
                buttons.append([
                    InlineKeyboardButton(
                        text=display_name,
                        callback_data=f"V|{p_id}|{user_id}|{chat_id}|{'1' if video else '0'}|{'1' if fplay else '0'}"
                    )
                ])
            buttons.append([InlineKeyboardButton(text="ᴄʟᴏsᴇ", callback_data="close")])
            return await mystic.edit_text(
                f"<b><blockquote>✨ sᴇᴀʀᴄʜ ʀᴇsᴜʟᴛs ғᴏʀ: <code>{query}</code>\n\nᴘʟᴇᴀsᴇ sᴇʟᴇᴄᴛ ᴀ ᴘʟᴀʏʟɪsᴛ ᴛᴏ ᴘʟᴀʏ:</blockquote></b>",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            return await mystic.edit_text(f"<b>🚫 ᴀᴘɪ ᴇʀʀᴏʀ:</b> <code>{e}</code>")

    # If no query and not 'mine'
    return await message.reply_text("<b>ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴘʟᴀʏʟɪsᴛ ɴᴀᴍᴇ ᴏʀ ᴜsᴇ</b> <code>/playplaylist mine</code>")

# --- CALLBACK: Move Playlist ---
@app.on_callback_query(filters.regex(r"^PlaylistMoveReq"))
async def playlist_move_req(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    playlist = await get_playlist(user_id)
    if not playlist:
        return await callback_query.answer("ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ ɪs ᴇᴍᴘᴛʏ!", show_alert=True)
        
    MOVE_PLAYLIST_STATES[user_id] = {"step": "waiting_target"}
    await callback_query.message.reply_text(
        "<blockquote><b>📤 Mᴏᴠᴇ Pʟᴀʏʟɪsᴛ</b>\n\nᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪᴛʜ ᴛʜᴇ ᴛᴇʟᴇɢʀᴀᴍ ᴜsᴇʀ ɪᴅ ᴏғ ᴛʜᴇ ᴜsᴇʀ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴍᴏᴠᴇ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ ᴛᴏ.</blockquote>",
        reply_markup=ForceReply(selective=True)
    )
    await callback_query.answer()

@app.on_message(filters.reply & filters.text & ~BANNED_USERS)
async def move_playlist_reply(client, message: Message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    if user_id in MOVE_PLAYLIST_STATES and MOVE_PLAYLIST_STATES[user_id].get("step") == "waiting_target":
        if not message.reply_to_message or message.reply_to_message.from_user.id != app.id:
            return
            
        target_id_str = message.text.strip()
        if not target_id_str.isdigit():
            return await message.reply_text("<blockquote><b>🚫 ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ</b>\n\nᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ɴᴜᴍᴇʀɪᴄ ᴛᴇʟᴇɢʀᴀᴍ ɪᴅ.</blockquote>")
            
        target_id = int(target_id_str)
        if target_id == user_id:
            return await message.reply_text("<blockquote><b>🚫 ɪɴᴠᴀʟɪᴅ ᴛʀᴀɴsғᴇʀ</b>\n\nʏᴏᴜ ᴄᴀɴɴᴏᴛ ᴍᴏᴠᴇ ᴀ ᴘʟᴀʏʟɪsᴛ ᴛᴏ ʏᴏᴜʀsᴇʟғ.</blockquote>")
            
        otp = str(random.randint(100000, 999999))
        MOVE_PLAYLIST_STATES[user_id] = {
            "step": "waiting_otp",
            "target_id": target_id,
            "otp": otp,
            "otp_entered": ""
        }
        
        try:
            await app.send_message(
                target_id,
                f"<blockquote><b>🔐 Pʟᴀʏʟɪsᴛ Tʀᴀɴsғᴇʀ Rᴇǫᴜᴇsᴛ</b>\n\nᴜsᴇʀ {message.from_user.mention} ᴡᴀɴᴛs ᴛᴏ ᴛʀᴀɴsғᴇʀ ᴛʜᴇɪʀ ᴀᴜʀᴇx ᴍᴜsɪᴄ ᴘʟᴀʏʟɪsᴛ ᴛᴏ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ.</blockquote>\n<blockquote>ᴛᴏ ᴀᴄᴄᴇᴘᴛ ᴛʜɪs ᴛʀᴀɴsғᴇʀ, ᴘʟᴇᴀsᴇ sʜᴀʀᴇ ᴛʜᴇ ғᴏʟʟᴏᴡɪɴɢ ᴏᴛᴘ ᴡɪᴛʜ ᴛʜᴇᴍ:\n\n<b>OTP:</b> <code>{otp}</code></blockquote>\n<blockquote><i>(Iғ ʏᴏᴜ ᴅᴏɴ'ᴛ ᴋɴᴏᴡ ᴛʜɪs ᴜsᴇʀ, ɪɢɴᴏʀᴇ ᴛʜɪs ᴍᴇssᴀɢᴇ.)</i></blockquote>"
            )
        except Exception as e:
            del MOVE_PLAYLIST_STATES[user_id]
            return await message.reply_text(f"<blockquote><b>🚫 ᴛʀᴀɴsғᴇʀ ғᴀɪʟᴇᴅ</b>\n\nғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ᴏᴛᴘ ᴛᴏ ᴛʜᴇ ᴛᴀʀɢᴇᴛ ᴜsᴇʀ. ᴍᴀᴋᴇ sᴜʀᴇ ᴛʜᴇʏ ʜᴀᴠᴇ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ɪɴ ᴅᴍ.\n\n<b>Eʀʀᴏʀ:</b> <code>{e}</code></blockquote>")
            
        await show_otp_panel(message.chat.id, message.id, user_id)

async def show_otp_panel(chat_id, reply_to_message_id, user_id):
    state = MOVE_PLAYLIST_STATES.get(user_id)
    if not state:
        return
        
    entered = state["otp_entered"]
    display_text = entered + "〇" * (6 - len(entered))
    text = f"<blockquote><b>🔐 Eɴᴛᴇʀ OTP</b>\n\nAɴ ᴏᴛᴘ ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ ᴛʜᴇ ᴛᴀʀɢᴇᴛ ᴜsᴇʀ's ᴅᴍ.\n\nᴘʟᴇᴀsᴇ ᴀsᴋ ᴛʜᴇᴍ ғᴏʀ ɪᴛ ᴀɴᴅ ᴇɴᴛᴇʀ ᴛʜᴇ 6-ᴅɪɢɪᴛ ᴏᴛᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴄᴏɴғɪʀᴍ ᴛʜᴇ ᴛʀᴀɴsғᴇʀ:\n\n<b>OTP:</b> <code>{display_text}</code></blockquote>"
    
    buttons = [
        [InlineKeyboardButton("1", callback_data="OTP 1"), InlineKeyboardButton("2", callback_data="OTP 2"), InlineKeyboardButton("3", callback_data="OTP 3")],
        [InlineKeyboardButton("4", callback_data="OTP 4"), InlineKeyboardButton("5", callback_data="OTP 5"), InlineKeyboardButton("6", callback_data="OTP 6")],
        [InlineKeyboardButton("7", callback_data="OTP 7"), InlineKeyboardButton("8", callback_data="OTP 8"), InlineKeyboardButton("9", callback_data="OTP 9")],
        [InlineKeyboardButton("Cʟᴇᴀʀ", callback_data="OTP clear"), InlineKeyboardButton("0", callback_data="OTP 0"), InlineKeyboardButton("Cᴀɴᴄᴇʟ", callback_data="OTP cancel")]
    ]
    await app.send_message(chat_id, text, reply_to_message_id=reply_to_message_id, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^OTP "))
async def otp_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data.split()[1]
    
    if user_id not in MOVE_PLAYLIST_STATES or MOVE_PLAYLIST_STATES[user_id].get("step") != "waiting_otp":
        return await callback_query.answer("Nᴏ ᴀᴄᴛɪᴠᴇ ᴘʟᴀʏʟɪsᴛ ᴛʀᴀɴsғᴇʀ.", show_alert=True)
        
    state = MOVE_PLAYLIST_STATES[user_id]
    
    if data == "cancel":
        del MOVE_PLAYLIST_STATES[user_id]
        return await callback_query.message.edit_text("<blockquote><b>🚫 ᴘʟᴀʏʟɪsᴛ ᴛʀᴀɴsғᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b></blockquote>")
        
    if data == "clear":
        state["otp_entered"] = ""
    else:
        if len(state["otp_entered"]) < 6:
            state["otp_entered"] += data
            
    entered = state["otp_entered"]
    
    if len(entered) == 6:
        if entered == state["otp"]:
            target_id = state["target_id"]
            playlist = await get_playlist(user_id)
            
            for track in playlist:
                await add_to_playlist(target_id, track)
            await clear_playlist(user_id)
            
            del MOVE_PLAYLIST_STATES[user_id]
            
            try:
                await app.send_message(target_id, f"<blockquote><b>Pʟᴀʏʟɪsᴛ Tʀᴀɴsғᴇʀʀᴇᴅ!</b>\n\nTʜᴇ ᴘʟᴀʏʟɪsᴛ ғʀᴏᴍ {callback_query.from_user.mention} ʜᴀs ʙᴇᴇɴ sᴜᴄᴄᴇssғᴜʟʟʏ ᴛʀᴀɴsғᴇʀʀᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ!</blockquote>")
            except:
                pass
            return await callback_query.message.edit_text("<blockquote><b>Pʟᴀʏʟɪsᴛ sᴜᴄᴄᴇssғᴜʟʟʏ ᴛʀᴀɴsғᴇʀʀᴇᴅ ᴛᴏ ᴛʜᴇ ᴛᴀʀɢᴇᴛ ᴜsᴇʀ!</b></blockquote>")
        else:
            state["otp_entered"] = ""
            await callback_query.answer("Iɴᴄᴏʀʀᴇᴄᴛ OTP! Tʀʏ ᴀɢᴀɪɴ.", show_alert=True)
            
    display_text = state["otp_entered"] + "〇" * (6 - len(state["otp_entered"]))
    text = f"<blockquote><b>🔐 Eɴᴛᴇʀ OTP</b>\n\nAɴ ᴏᴛᴘ ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ ᴛʜᴇ ᴛᴀʀɢᴇᴛ ᴜsᴇʀ's ᴅᴍ.\n\nᴘʟᴇᴀsᴇ ᴀsᴋ ᴛʜᴇᴍ ғᴏʀ ɪᴛ ᴀɴᴅ ᴇɴᴛᴇʀ ᴛʜᴇ 6-ᴅɪɢɪᴛ ᴏᴛᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴄᴏɴғɪʀᴍ ᴛʜᴇ ᴛʀᴀɴsғᴇʀ:\n\n<b>OTP:</b> <code>{display_text}</code></blockquote>"
    
    buttons = [
        [InlineKeyboardButton("1", callback_data="OTP 1"), InlineKeyboardButton("2", callback_data="OTP 2"), InlineKeyboardButton("3", callback_data="OTP 3")],
        [InlineKeyboardButton("4", callback_data="OTP 4"), InlineKeyboardButton("5", callback_data="OTP 5"), InlineKeyboardButton("6", callback_data="OTP 6")],
        [InlineKeyboardButton("7", callback_data="OTP 7"), InlineKeyboardButton("8", callback_data="OTP 8"), InlineKeyboardButton("9", callback_data="OTP 9")],
        [InlineKeyboardButton("Cʟᴇᴀʀ", callback_data="OTP clear"), InlineKeyboardButton("0", callback_data="OTP 0"), InlineKeyboardButton("Cᴀɴᴄᴇʟ", callback_data="OTP cancel")]
    ]
    
    try:
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        pass
    await callback_query.answer()
