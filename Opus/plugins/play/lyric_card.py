import os
import time
import io
import asyncio
import requests
from typing import Union
from pyrogram import filters
from pyrogram.types import CallbackQuery, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
from config import BANNED_USERS
from Opus import app
from Opus.misc import db
from Opus.utils.database import is_active_chat
from Opus.utils.decorators.language import languageCB

def download_poppins_fonts():
    font_bold_path = "cache/Poppins-Bold.ttf"
    font_medium_path = "cache/Poppins-Medium.ttf"
    
    urls = {
        font_bold_path: "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf",
        font_medium_path: "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf"
    }
    
    for path, url in urls.items():
        if not os.path.exists(path):
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    with open(path, "wb") as f:
                        f.write(resp.content)
            except Exception as e:
                print(f"Error downloading Poppins font {path}: {e}")

# Trigger font download immediately on import
download_poppins_fonts()

def get_font(size, bold=False):
    # Try premium Poppins fonts for full Hindi/Unicode support
    poppins_bold = "cache/Poppins-Bold.ttf"
    poppins_medium = "cache/Poppins-Medium.ttf"
    
    target = poppins_bold if bold else poppins_medium
    if os.path.exists(target):
        try:
            return ImageFont.truetype(target, size)
        except:
            pass
            
    # Fallbacks for system compatibility
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                pass
    try:
        return ImageFont.load_default()
    except:
        return None

def fetch_high_res_cover(videoid, thumbnail_url=None):
    # Check if videoid is empty, or if it is a non-YouTube platform track
    if not videoid or any(x in videoid for x in ["spotify", "apple", "vortex", "index", "telegram", "soundcloud"]):
        if thumbnail_url and thumbnail_url.startswith("http"):
            return thumbnail_url
        return None
        
    # Check YouTube high-res maxresdefault first
    url_max = f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg"
    try:
        resp = requests.head(url_max, timeout=3)
        if resp.status_code == 200:
            return url_max
    except:
        pass
        
    return f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg"

def generate_lyric_card(album_art_url_or_path, title, performer, played_sec, duration_sec, lyric_lines):
    album_art = None
    if album_art_url_or_path:
        if os.path.exists(album_art_url_or_path):
            try:
                album_art = Image.open(album_art_url_or_path)
            except:
                pass
        elif album_art_url_or_path.startswith("http"):
            try:
                resp = requests.get(album_art_url_or_path, timeout=5)
                if resp.status_code == 200:
                    album_art = Image.open(io.BytesIO(resp.content))
            except:
                pass
                
    if not album_art:
        # Create premium placeholder gradient
        album_art = Image.new("RGB", (1080, 1920), color=(18, 18, 24))
        draw = ImageDraw.Draw(album_art)
        for y in range(1920):
            r = int(18 + (30 - 18) * (y / 1920))
            g = int(18 + (30 - 18) * (y / 1920))
            b = int(24 + (45 - 24) * (y / 1920))
            draw.line([(0, y), (1080, y)], fill=(r, g, b))

    # Resize background to portrait size and apply powerful Gaussian blur
    bg = album_art.resize((1080, 1920)).filter(ImageFilter.GaussianBlur(75))
    
    # Overlay elegant dark wash for premium contrast
    overlay = Image.new("RGBA", (1080, 1920), (10, 10, 12, 145))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)
    
    draw = ImageDraw.Draw(bg)
    
    # --- 1. HEADER WATERMARK ---
    header_text = "S T O R M I F Y 26.5"
    header_font = get_font(22, bold=True)
    header_w = draw.textlength(header_text, font=header_font)
    draw.text(((1080 - header_w) // 2, 140), header_text, fill=(255, 255, 255, 140), font=header_font)
    
    # --- 2. ALBUM ART COVER WITH DYNAMIC GLOW SHADOW ---
    cover_size = 660
    cover = album_art.resize((cover_size, cover_size))
    
    # Draw soft outer drop shadow for the cover
    shadow_offset = 15
    shadow = Image.new("RGBA", (cover_size + shadow_offset * 4, cover_size + shadow_offset * 4), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rounded_rectangle(
        [(shadow_offset * 2, shadow_offset * 2), (cover_size + shadow_offset * 2, cover_size + shadow_offset * 2)],
        radius=46,
        fill=(0, 0, 0, 130)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    
    # Paste drop shadow
    cover_x = (1080 - cover_size) // 2
    cover_y = 260
    bg.paste(shadow, (cover_x - shadow_offset * 2, cover_y - shadow_offset * 2), shadow)
    
    # Crop rounded cover art with sleek thin border
    mask = Image.new("L", (cover_size, cover_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (cover_size, cover_size)], radius=42, fill=255)
    bg.paste(cover, (cover_x, cover_y), mask)
    
    # Sleek outline border
    draw.rounded_rectangle(
        [(cover_x, cover_y), (cover_x + cover_size, cover_y + cover_size)],
        radius=42,
        outline=(255, 255, 255, 30),
        width=3
    )
    
    # --- 3. SONG DETAILS (Full Hindi / Unicode Support) ---
    title_font = get_font(44, bold=True)
    artist_font = get_font(28)
    
    if len(title) > 34:
        title = title[:31] + "..."
    if len(performer) > 40:
        performer = performer[:37] + "..."
        
    title_w = draw.textlength(title, font=title_font)
    title_x = (1080 - title_w) // 2
    
    # Subtle drop shadow for title text
    draw.text((title_x + 2, 985 + 2), title, fill=(0, 0, 0, 160), font=title_font)
    draw.text((title_x, 985), title, fill=(255, 255, 255, 255), font=title_font)
    
    artist_w = draw.textlength(performer, font=artist_font)
    artist_x = (1080 - artist_w) // 2
    draw.text((artist_x, 1050), performer, fill=(210, 210, 220, 220), font=artist_font)
    
    # --- 4. SEEK BAR VISUALIZER WITH ACTIVE SCROLLER HANDLE ---
    bar_width = 860
    bar_height = 20
    bar_x = (1080 - bar_width) // 2
    bar_y = 1150
    
    progress = 0.0
    if duration_sec > 0:
        progress = max(0.0, min(1.0, played_sec / duration_sec))
        
    # Create transparent seekbar overlay for premium alpha compositing
    bar_overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    bar_draw = ImageDraw.Draw(bar_overlay)

    # Draw glassy translucent white background track
    bar_draw.rounded_rectangle(
        [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
        radius=bar_height // 2,
        fill=(255, 255, 255, 64) # Soft glassy white (25% opacity)
    )
    if progress > 0:
        active_w = int(bar_width * progress)
        if active_w >= bar_height:
            # Fill active track with solid white
            bar_draw.rounded_rectangle(
                [(bar_x, bar_y), (bar_x + active_w, bar_y + bar_height)],
                radius=bar_height // 2,
                fill=(255, 255, 255, 255)
            )
        elif active_w > 0:
            # Draw tiny dot if early in playback
            bar_draw.rounded_rectangle(
                [(bar_x, bar_y), (bar_x + bar_height, bar_y + bar_height)],
                radius=bar_height // 2,
                fill=(255, 255, 255, 255)
            )

    # Merge overlay with main canvas
    bg = Image.alpha_composite(bg, bar_overlay)
    draw = ImageDraw.Draw(bg)
        
    # Duration Timers underneath seekbar
    def format_time(seconds):
        mins = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{mins}:{secs:02d}"
        
    time_font = get_font(20)
    played_str = format_time(played_sec)
    total_str = format_time(duration_sec) if duration_sec > 0 else "0:00"
    
    draw.text((bar_x, bar_y + 30), played_str, fill=(255, 255, 255, 160), font=time_font)
    total_w = draw.textlength(total_str, font=time_font)
    draw.text((bar_x + bar_width - total_w, bar_y + 30), total_str, fill=(255, 255, 255, 160), font=time_font)
    
    # --- 5. ULTRA-PREMIUM LYRICS LAYOUT (Replaced with random beautiful musical quote sets) ---
    import random
    quote_sets = [
        [
            ("I STILL HEAR YOUR MELODY", False),
            ("IN EVERY SILENT CORNER OF MY MIND.", True),
            ("SOME SONGS NEVER TRULY END.", False)
        ],
        [
            ("LOST IN A WORLD OF ECHOES,", False),
            ("BUT YOUR VOICE IS THE ONLY SOUND", True),
            ("THAT KEEPS ME FROM DRIFTING AWAY.", False)
        ],
        [
            ("YOU ARE THE RHYTHM", False),
            ("MY HEART HAS BEEN SEARCHING FOR.", True),
            ("A PERFECT SYMPHONY OF US.", False)
        ],
        [
            ("MIDNIGHT PLAYLISTS AND COLD TEA,", False),
            ("THINKING OF THE WORDS", True),
            ("WE NEVER GOT TO SING OUT LOUD.", False)
        ],
        [
            ("THE MUSIC WASHES OVER ME,", False),
            ("A SWEET ESCAPE FROM THE NOISE", True),
            ("OF A WORLD THAT NEVER SLEEPS.", False)
        ],
        [
            ("DANCING IN THE NEON SHADOWS,", False),
            ("HEARING YOUR NAME", True),
            ("IN EVERY FADING BEAT.", False)
        ],
        [
            ("IF SOULS HAD A SOUNDTRACK,", False),
            ("YOURS WOULD BE MY FAVORITE SONG.", True),
            ("WRITTEN IN THE STARS.", False)
        ]
    ]
    display_lines = random.choice(quote_sets)

    lyric_font_main = get_font(38, bold=True)
    lyric_font_side = get_font(28)
    
    y_coordinates = [1290, 1390, 1490]
    
    for idx, (line_text, is_active) in enumerate(display_lines):
        if len(line_text) > 46:
            line_text = line_text[:43] + "..."
            
        font = lyric_font_main if is_active else lyric_font_side
        color = (255, 255, 255, 255) if is_active else (255, 255, 255, 110)
        
        w = draw.textlength(line_text, font=font)
        x = (1080 - w) // 2
        y = y_coordinates[idx]
        
        if is_active:
            # Subtle back glow for active lyric to pop from screen
            draw.text((x + 2, y + 2), line_text, fill=(0, 0, 0, 130), font=font)
            
        draw.text((x, y), line_text, fill=color, font=font)
        
    # --- 6. FOOTER QUOTE & WATERMARK ---
    quote_text = "Crafted to be heard.  Built to be felt."
    quote_font = get_font(22, bold=True)
    quote_w = draw.textlength(quote_text, font=quote_font)
    draw.text(((1080 - quote_w) // 2, 1720), quote_text, fill=(255, 255, 255, 140), font=quote_font)
    
    output_path = f"cache/lyric_card_{int(time.time())}.jpg"
    bg.convert("RGB").save(output_path, "JPEG", quality=95)
    return output_path

# Rate limiting dictionary for share card (user_id -> last_timestamp)
SHARE_CARD_LIMIT = {}

@app.on_callback_query(filters.regex("ShareLyricCard") & ~BANNED_USERS)
@languageCB
async def share_lyric_card_cb(client, CallbackQuery: CallbackQuery, _):
    user_id = CallbackQuery.from_user.id
    now = time.time()
    if user_id in SHARE_CARD_LIMIT:
        elapsed = now - SHARE_CARD_LIMIT[user_id]
        if elapsed < 60:
            remaining = int(60 - elapsed)
            return await CallbackQuery.answer(
                f"⏳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining}s ʙᴇғᴏʀᴇ sʜᴀʀɪɴɢ ᴀɴᴏᴛʜᴇʀ ᴄᴀʀᴅ.",
                show_alert=True
            )
            
    SHARE_CARD_LIMIT[user_id] = now
    callback_data = CallbackQuery.data.strip()
    videoid = callback_data.split(None, 1)[1]
    chat_id = CallbackQuery.message.chat.id
    
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
        
    playing = db.get(chat_id)
    if not playing:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
        
    await CallbackQuery.answer("🎨 ɢᴇɴᴇʀᴀᴛɪɴɢ ʏᴏᴜʀ ᴀᴜʀᴇx sᴛᴏʀʏ ᴄᴀʀᴅ...")
    
    # Gather Track Info
    title = playing[0].get("title", "Unknown Track")
    performer = playing[0].get("performer", "Aurex Music")
    played_sec = playing[0].get("played", 0)
    duration_sec = playing[0].get("seconds", 0)
    thumbnail = playing[0].get("thumb")
    
    # Dynamic high-resolution cover artwork from YouTube on the fly
    cover_art_path = fetch_high_res_cover(videoid, thumbnail)
        
    # Dynamic On-The-Fly Sync lyrics retriever to prevent empty states
    synced = playing[0].get("synced_lyrics")
    if not synced:
        try:
            from Opus.platforms.Lyrics import Lyrics
            synced = await Lyrics.get_synced_lyrics(title)
            if synced:
                playing[0]["synced_lyrics"] = synced
        except Exception as e:
            print(f"Error fetching lyrics on the fly: {e}")
            
    lyric_lines = []
    
    if synced and isinstance(synced, list):
        active_idx = -1
        for i, (l_sec, text) in enumerate(synced):
            if played_sec >= l_sec:
                active_idx = i
            else:
                break
                
        if active_idx != -1:
            prev_text = synced[active_idx - 1][1] if active_idx > 0 else ""
            active_text = synced[active_idx][1]
            next_text = synced[active_idx + 1][1] if active_idx < len(synced) - 1 else ""
            
            lyric_lines = [
                (prev_text, False),
                (active_text, True),
                (next_text, False)
            ]
            
    if not lyric_lines:
        plain = playing[0].get("plain_lyrics")
        if plain and isinstance(plain, str):
            lines = [l.strip() for l in plain.split("\n") if l.strip() and len(l.strip()) > 3]
            if lines:
                idx = (played_sec // 12) % len(lines)
                prev_text = lines[idx - 1] if idx > 0 else ""
                active_text = lines[idx]
                next_text = lines[idx + 1] if idx < len(lines) - 1 else ""
                
                lyric_lines = [
                    (prev_text, False),
                    (active_text, True),
                    (next_text, False)
                ]
                
    if not lyric_lines:
        # Breathtaking default fallback phrases
        lyric_lines = [
            ("( Music Playing )", False),
            ("Feel the frequency, embrace the sound.", True),
            ("Aurex Premium Acoustic Experience.", False)
        ]
        
    try:
        # Run card creation in thread pool
        card_path = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_lyric_card(
                cover_art_path,
                title,
                performer,
                played_sec,
                duration_sec,
                lyric_lines
            )
        )
    except Exception as e:
        loop = asyncio.get_event_loop()
        card_path = await loop.run_in_executor(
            None,
            lambda: Image.new("RGB", (1080, 1920), (18, 18, 24)).convert("RGB").save(f"cache/lyric_card_{int(time.time())}.jpg", "JPEG") or f"cache/lyric_card_{int(time.time())}.jpg"
        )
        try:
            bg = Image.new("RGB", (1080, 1920), color=(18, 18, 24))
            draw = ImageDraw.Draw(bg)
            title_font = get_font(40, bold=True)
            artist_font = get_font(26)
            draw.text((100, 450), title, fill=(255,255,255), font=title_font)
            draw.text((100, 520), performer, fill=(200,200,200), font=artist_font)
            for idx, (lt, act) in enumerate(lyric_lines):
                draw.text((100, 650 + idx * 60), lt, fill=(255,255,255) if act else (150,150,150), font=get_font(28, bold=act))
            card_path = f"cache/lyric_card_{int(time.time())}.jpg"
            bg.save(card_path, "JPEG")
        except:
            pass

    # Send the premium visual card as photo!
    if os.path.exists(card_path):
        btn_title = title
        if len(btn_title) > 28:
            btn_title = btn_title[:25] + "..."
        btn_perf = performer
        if len(btn_perf) > 22:
            btn_perf = btn_perf[:19] + "..."
            
        await client.send_photo(
            chat_id=chat_id,
            photo=card_path,
            reply_to_message_id=CallbackQuery.message.id
        )
        try:
            os.remove(card_path)
        except:
            pass
    else:
        await CallbackQuery.answer("Failed to generate card due to rendering issues. ❌", show_alert=True)
