import os
import time
import httpx
import asyncio
import glob
import shutil
import unicodedata
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from unidecode import unidecode

from config import BANNED_USERS
from Opus import app
from Opus.utils.database import get_user_stats, get_leaderboard
from Opus.plugins.play.lyric_card import get_font
from Opus.utils.thumbnails import remove_black_bars

# Global Leaderboard image caching system
LEADERBOARD_CACHE = {}
LEADERBOARD_CACHE_EXPIRY = 300  # 5 minutes cache duration

# Rate limiting dictionaries for stats and leaderboards (user_id -> last_timestamp)
STATS_LIMIT = {}
LEADERBOARD_LIMIT = {}

def has_special_characters(s: str) -> bool:
    if not s:
        return False
    for char in s:
        if ord(char) > 127:
            return True
    return False

def resolve_unicode_fallbacks(text: str) -> str:
    if not text:
        return ""
    small_caps = {
        'ᴀ': 'A', 'ʙ': 'B', 'ᴄ': 'C', 'ᴅ': 'D', 'ᴇ': 'E', 'ꜰ': 'F', 'ɢ': 'G', 'ʜ': 'H', 'ɪ': 'I',
        'ᴊ': 'J', 'ᴋ': 'K', 'ʟ': 'L', 'ᴍ': 'M', 'ɴ': 'N', 'ᴏ': 'O', 'ᴘ': 'P', 'ǫ': 'Q', 'ʀ': 'R',
        'ꜱ': 'S', 'ᴛ': 'T', 'ᴜ': 'U', 'ᴠ': 'V', 'ᴡ': 'W', 'x': 'X', 'ʏ': 'Y', 'ᴢ': 'Z'
    }
    res = []
    for char in text:
        if char in small_caps:
            res.append(small_caps[char])
        else:
            res.append(char)
    return "".join(res)

def clean_unicode_name(name: str) -> str:
    if not name:
        return ""
    # Normalize Unicode compatibility characters first (e.g. mathematical bold/monospace/script to normal letters)
    name = unicodedata.normalize('NFKD', name)
    name = resolve_unicode_fallbacks(name)
    return name.strip()

def get_fallback_fonts(size):
    fonts = []
    for font_path in [
        "/System/Library/Fonts/Supplemental/STIXTwoMath.otf",
        "/System/Library/Fonts/Supplemental/STIXGeneral.otf",
        "/System/Library/Fonts/Apple Symbols.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc"
    ]:
        if os.path.exists(font_path):
            try:
                fonts.append(ImageFont.truetype(font_path, size))
            except:
                pass
    return fonts

def draw_text_with_fallback(draw, xy, text, fill, standard_font, loaded_fonts, is_upper=False, shadow_fill=None, center_width=None):
    display_text = text.upper() if is_upper else text
    
    all_fonts = []
    if standard_font:
        all_fonts.append(standard_font)
    for f in loaded_fonts:
        if f not in all_fonts:
            all_fonts.append(f)
            
    # Cache missing masks by font ID for ultimate speed
    _missing_masks = {}
    def char_supported(font, char) -> bool:
        if not font:
            return False
        try:
            f_key = id(font)
            if f_key not in _missing_masks:
                _missing_masks[f_key] = list(font.getmask('\uffff'))
            return list(font.getmask(char)) != _missing_masks[f_key]
        except:
            return False

    total_width = 0
    char_font_pairs = []
    
    for char in display_text:
        best_font = None
        display_char = char
        
        # Prefer standard font for standard ASCII characters
        if ord(char) <= 127:
            if standard_font and char_supported(standard_font, char):
                best_font = standard_font
                
        if not best_font:
            for font in all_fonts:
                if char_supported(font, char):
                    best_font = font
                    break
                    
        # If still not supported by any fallback font, decompose to basic Latin letter
        if not best_font:
            display_char = unidecode(unicodedata.normalize('NFKD', char))
            best_font = standard_font
            
        char_width = draw.textlength(display_char, font=best_font)
        total_width += char_width
        char_font_pairs.append((display_char, best_font, char_width))
        
    start_x, y = xy
    if center_width is not None:
        start_x = (center_width - total_width) // 2
        
    current_x = start_x
    for display_char, font, char_width in char_font_pairs:
        if shadow_fill:
            draw.text((current_x + 2, y + 2), display_char, fill=shadow_fill, font=font)
        draw.text((current_x, y), display_char, fill=fill, font=font)
        current_x += char_width
        
    return total_width

def draw_mini_player_card(cover_path, title, artist):
    # Dimensions of the premium mini player card
    card_w, card_h = 320, 520
    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card)
    
    # Load and clean cover art
    cover_img = None
    if cover_path and os.path.exists(cover_path):
        try:
            cover_img = Image.open(cover_path).convert("RGBA")
        except:
            pass
            
    if not cover_img:
        # Fallback record placeholder artwork
        cover_img = Image.new("RGBA", (280, 280), (40, 40, 40, 255))
        cx, cy = 140, 140
        ImageDraw.Draw(cover_img).ellipse((cx - 100, cy - 100, cx + 100, cy + 100), fill=(20, 20, 20, 255), outline=(255, 255, 255, 100), width=3)
        ImageDraw.Draw(cover_img).ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=(255, 182, 193, 255))
    
    # Clean black bars and crop to perfect square
    cover_img = remove_black_bars(cover_img)
    w_c, h_c = cover_img.size
    min_side = min(w_c, h_c)
    cover_sq = cover_img.crop(((w_c - min_side) // 2, (h_c - min_side) // 2, (w_c + min_side) // 2, (h_c + min_side) // 2))
    cover_sq = cover_sq.resize((272, 272), Image.Resampling.LANCZOS)
    
    # Calculate dominant average color for dynamic dynamic card background
    from Opus.utils.thumbnails import _most_common_colors
    colors = _most_common_colors(cover_sq, n=1)
    dom_color = colors[0] if colors else (40, 30, 35)
    # Scale color to luxury dark tint
    bg_r = int(dom_color[0] * 0.45 + 15)
    bg_g = int(dom_color[1] * 0.45 + 10)
    bg_b = int(dom_color[2] * 0.45 + 15)
    card_bg_color = (bg_r, bg_g, bg_b, 255)
    
    # Draw rounded player card background
    c_draw.rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=24, fill=card_bg_color)
    
    # Paste rounded cover art (x=24, y=24)
    cover_mask = Image.new("L", (272, 272), 0)
    ImageDraw.Draw(cover_mask).rounded_rectangle((0, 0, 272, 272), radius=16, fill=255)
    card.paste(cover_sq, (24, 24), cover_mask)
    
    # Write Song Title (White, bold, size 18)
    title_font = get_font(18, bold=True)
    clean_title = clean_unicode_name(title)
    if len(clean_title) > 22:
        clean_title = clean_title[:20] + "..."
    title_fallbacks = get_fallback_fonts(18)
    draw_text_with_fallback(c_draw, (24, 315), clean_title, (255, 255, 255, 255), title_font, title_fallbacks, is_upper=True)
    
    # Write Artist/Subtitle (Translucent white, size 15)
    artist_font = get_font(15)
    clean_artist = clean_unicode_name(artist)
    if len(clean_artist) > 28:
        clean_artist = clean_artist[:26] + "..."
    artist_fallbacks = get_fallback_fonts(15)
    draw_text_with_fallback(c_draw, (24, 345), clean_artist, (255, 255, 255, 140), artist_font, artist_fallbacks, is_upper=True)
    
    # Draw Mini Seekbar Progress line (x=24 to 296, y=390)
    progress_y = 390
    c_draw.rounded_rectangle((24, progress_y, 296, progress_y + 4), radius=2, fill=(255, 255, 255, 40))
    import random
    prog_width = random.randint(40, 180)
    c_draw.rounded_rectangle((24, progress_y, 24 + prog_width, progress_y + 4), radius=2, fill=(255, 255, 255, 255))
    c_draw.ellipse((24 + prog_width - 4, progress_y - 2, 24 + prog_width + 4, progress_y + 6), fill=(255, 255, 255, 255))
    
    # Draw Mini Media Controls (x=160 center, y=440)
    cx, cy = 160, 445
    c_draw.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), fill=(255, 255, 255, 255))
    c_draw.rectangle((cx - 6, cy - 9, cx - 2, cy + 9), fill=(0, 0, 0, 255))
    c_draw.rectangle((cx + 2, cy - 9, cx + 6, cy + 9), fill=(0, 0, 0, 255))
    
    # Previous (Triangles)
    prev_cx = cx - 70
    c_draw.polygon([(prev_cx - 4, cy), (prev_cx + 8, cy - 9), (prev_cx + 8, cy + 9)], fill=(255, 255, 255, 220))
    c_draw.polygon([(prev_cx - 16, cy), (prev_cx - 4, cy - 9), (prev_cx - 4, cy + 9)], fill=(255, 255, 255, 220))
    
    # Next (Triangles)
    next_cx = cx + 70
    c_draw.polygon([(next_cx + 4, cy), (next_cx - 8, cy - 9), (next_cx - 8, cy + 9)], fill=(255, 255, 255, 220))
    c_draw.polygon([(next_cx + 16, cy), (next_cx + 4, cy - 9), (next_cx + 4, cy + 9)], fill=(255, 255, 255, 220))
    
    # Shuffle & Repeat indicators
    c_draw.text((28, cy - 10), "⇄", fill=(255, 255, 255, 140), font=get_font(20))
    c_draw.text((264, cy - 10), "↻", fill=(255, 255, 255, 140), font=get_font(20))
    
    return card

def generate_wrapped_card(user_name, total_played, top_songs, avatar_path=None, collage_data=None):
    # 1. Create a beautiful base canvas with luxury dark charcoal-rose color
    bg = Image.new("RGB", (1080, 1920), color=(28, 18, 22))
    # 2. Render vibrant, messy scattered background collage of player cards (16 overlapping cards, filling the entire portrait background!)
    collage_layer = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    if collage_data:
        # Densely packed 20-card messy scattered layout — every inch of the background is covered!
        positions = [
            # Row 1: Top (y ~ -160 to -60)
            (-80, -100, -15),      # 1. Top left
            (200, -140, 8),        # 2. Top center-left
            (500, -120, -10),      # 3. Top center-right
            (800, -60, 12),        # 4. Top right
            # Row 2: Upper (y ~ 280 to 420)
            (-100, 280, 14),       # 5. Upper left
            (200, 320, -7),        # 6. Upper center-left
            (520, 280, 5),         # 7. Upper center-right
            (830, 350, -12),       # 8. Upper right
            # Row 3: Middle (y ~ 650 to 800) — the previously empty zone!
            (-80, 680, -10),       # 9. Mid left
            (180, 720, 8),         # 10. Mid center-left
            (500, 660, -5),        # 11. Mid center-right
            (820, 700, 12),        # 12. Mid right
            # Row 4: Lower-mid (y ~ 1050 to 1200)
            (-120, 1080, 12),      # 13. Lower-mid left
            (200, 1120, -8),       # 14. Lower-mid center-left
            (520, 1060, 6),        # 15. Lower-mid center-right
            (840, 1100, -14),      # 16. Lower-mid right
            # Row 5: Bottom (y ~ 1450 to 1750)
            (-60, 1480, -10),      # 17. Bottom left
            (250, 1520, 7),        # 18. Bottom center-left
            (540, 1460, -6),       # 19. Bottom center-right
            (800, 1500, 15),       # 20. Bottom right
        ]
        
        for idx in range(len(positions)):
            if not collage_data:
                break
            # Cycle through available tracks if user has fewer tracks than slots
            item = collage_data[idx % len(collage_data)]
            title, artist, path = item
            if os.path.exists(path):
                try:
                    # Generate dynamic, color-matched player card
                    card_img = draw_mini_player_card(path, title, artist)
                    
                    px, py, angle = positions[idx]
                    
                    # Rotate the player card with high-quality resampling and transparency preservation
                    rotated_card = card_img.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
                    
                    # Compute size differences to keep the rotated card centered at px, py
                    orig_w, orig_h = card_img.size
                    rot_w, rot_h = rotated_card.size
                    dx = (rot_w - orig_w) // 2
                    dy = (rot_h - orig_h) // 2
                    
                    collage_layer.paste(rotated_card, (px - dx, py - dy), rotated_card)
                except Exception as e:
                    print(f"Error processing background collage card: {e}")
                    
    # Composite collage onto base canvas (completely unblurred for premium visual richness!)
    bg = Image.alpha_composite(bg.convert("RGBA"), collage_layer)
    
    # Elegant blush pink dark wash overlay
    overlay = Image.new("RGBA", (1080, 1920), (28, 16, 22, 165))
    bg = Image.alpha_composite(bg, overlay)
    
    # Add ambient blush pink glows
    glow = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow)
    g_draw.ellipse((100, 100, 980, 980), fill=(255, 182, 193, 28))
    g_draw.ellipse((100, 900, 980, 1780), fill=(255, 182, 193, 20))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    bg = Image.alpha_composite(bg, glow)
    
    draw = ImageDraw.Draw(bg)
    
    # 3. Header Title (Pure crisp white with drop shadow for premium readability)
    header_text = "S T O R M I F Y   W R A P P E D"
    header_font = get_font(24, bold=True)
    header_w = draw.textlength(header_text, font=header_font)
    draw.text(((1080 - header_w) // 2 + 2, 120 + 2), header_text, fill=(0, 0, 0, 100), font=header_font)
    draw.text(((1080 - header_w) // 2, 120), header_text, fill=(255, 255, 255, 255), font=header_font) # Pure White
    
    # 4. Avatar / Profile Picture handling
    avatar_y = 200
    avatar_size = 240
    if avatar_path and os.path.exists(avatar_path):
        try:
            av_img = Image.open(avatar_path).convert("RGBA").resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
            
            # Mask to circle
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            
            av_x = (1080 - avatar_size) // 2
            
            # Smooth drop shadow under avatar
            av_shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
            av_s_draw = ImageDraw.Draw(av_shadow)
            av_s_draw.ellipse((av_x + 6, avatar_y + 6, av_x + avatar_size + 6, avatar_y + avatar_size + 6), fill=(0, 0, 0, 60))
            av_shadow = av_shadow.filter(ImageFilter.GaussianBlur(10))
            bg = Image.alpha_composite(bg, av_shadow)
            
            # Paste avatar
            bg.paste(av_img, (av_x, avatar_y), mask)
            draw = ImageDraw.Draw(bg)
            
            # Glowing border around circular avatar (Solid pure white for a clean, unified look)
            draw.ellipse((av_x - 4, avatar_y - 4, av_x + avatar_size + 4, avatar_y + avatar_size + 4), outline=(255, 255, 255, 255), width=6)
        except Exception as e:
            print(f"Error drawing avatar on wrapped card: {e}")
            
    # 5. User's Journey Subtitle
    if has_special_characters(user_name):
        # Pure copy-paste: preserve the user's custom casing and characters exactly
        name_str = f"{user_name}'s"
    else:
        name_str = f"{user_name.upper()}'S"
        
    name_size = max(32, min(52, int(52 - (len(name_str) - 14) * 1.5))) if len(name_str) > 14 else 52
    name_standard_font = get_font(name_size, bold=True)
    name_fallback_fonts = get_fallback_fonts(name_size)
    
    draw_text_with_fallback(
        draw,
        (0, 480),
        name_str,
        (255, 255, 255, 255),
        name_standard_font,
        name_fallback_fonts,
        shadow_fill=(0, 0, 0, 100),
        center_width=1080
    )
    
    sub_str = "MUSIC JOURNEY"
    sub_font = get_font(36, bold=True)
    sub_w = draw.textlength(sub_str, font=sub_font)
    # Subtitle drop shadow (Solid pure white text)
    draw.text(((1080 - sub_w) // 2 + 2, 550 + 2), sub_str, fill=(0, 0, 0, 100), font=sub_font)
    draw.text(((1080 - sub_w) // 2, 550), sub_str, fill=(255, 255, 255, 255), font=sub_font) # Pure White
    
    # 6. Card coordinates
    panel1_x1, panel1_y1 = 110, 640
    panel1_x2, panel1_y2 = 970, 840
    
    panel2_x1, panel2_y1 = 110, 880
    panel2_x2, panel2_y2 = 970, 1640
    
    # Floating shadow layer for both solid panels (creates spectacular Apple/Spotify depth!)
    shadow_layer = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_layer)
    s_draw.rounded_rectangle(
        [(panel1_x1 + 8, panel1_y1 + 8), (panel1_x2 + 8, panel1_y2 + 8)],
        radius=32,
        fill=(0, 0, 0, 45)
    )
    s_draw.rounded_rectangle(
        [(panel2_x1 + 8, panel2_y1 + 8), (panel2_x2 + 8, panel2_y2 + 8)],
        radius=32,
        fill=(0, 0, 0, 45)
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(15))
    bg = Image.alpha_composite(bg.convert("RGBA"), shadow_layer)
    
    # Create semi-transparent white panels
    panel_overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(panel_overlay)
    
    # Semi-transparent white panel 1 (Borderless for the ultimate clean aesthetic!)
    p_draw.rounded_rectangle(
        [(panel1_x1, panel1_y1), (panel1_x2, panel1_y2)],
        radius=32,
        fill=(255, 255, 255, 235), # Premium semi-transparent warm white (extremely clean!)
        outline=None,
    )
    
    # Semi-transparent white panel 2 (Borderless for the ultimate clean aesthetic!)
    p_draw.rounded_rectangle(
        [(panel2_x1, panel2_y1), (panel2_x2, panel2_y2)],
        radius=32,
        fill=(255, 255, 255, 235), # Premium semi-transparent warm white (extremely clean!)
        outline=None,
    )
    
    # Composite panels
    bg = Image.alpha_composite(bg, panel_overlay)
    draw = ImageDraw.Draw(bg)
    
    # Add Panel 1 Stats Content (High-contrast clean black typography)
    lbl_font = get_font(24, bold=True)
    lbl_text = "TOTAL TRACKS STREAMED"
    lbl_w = draw.textlength(lbl_text, font=lbl_font)
    draw.text(((1080 - lbl_w) // 2, 680), lbl_text, fill=(100, 100, 100, 255), font=lbl_font) # Clean Charcoal text
    
    stat_font = get_font(72, bold=True)
    stat_text = str(total_played)
    stat_w = draw.textlength(stat_text, font=stat_font)
    draw.text(((1080 - stat_w) // 2, 725), stat_text, fill=(0, 0, 0, 255), font=stat_font) # Pure Black streams number
    
    # Add Panel 2 Top Songs Content
    top_lbl = "YOUR TOP VIBES"
    top_lbl_font = get_font(28, bold=True)
    top_lbl_w = draw.textlength(top_lbl, font=top_lbl_font)
    draw.text(((1080 - top_lbl_w) // 2, 920), top_lbl, fill=(0, 0, 0, 255), font=top_lbl_font) # Pure Black label
    
    # Render top 5 songs inside panel 2 with unblurred cover art
    song_title_font = get_font(28, bold=True)
    song_count_font = get_font(22)
    
    start_y = 1000
    y_gap = 120
    
    for idx, song_data in enumerate(top_songs[:5]):
        # song_data is a tuple: (title, count, thumb_path)
        title_text, play_count, thumb_path = song_data
        
        # Draw Rank Number Badge (direct, clean, normal font counting - no circles!)
        idx_str = str(idx + 1)
        idx_f = get_font(34, bold=True)
        idx_w = draw.textlength(idx_str, font=idx_f)
        draw.text((150 + (30 - idx_w) // 2, start_y + idx * y_gap - 2), idx_str, fill=(0, 0, 0, 255), font=idx_f)
        
        # Draw unblurred square rounded song cover art
        art_size = 100
        art_x = 220
        art_y = start_y + idx * y_gap - 35
        art_drawn = False
        
        if thumb_path and os.path.exists(thumb_path):
            try:
                art_img = Image.open(thumb_path).convert("RGBA")
                # Remove black bars from cover art explicitly
                art_img = remove_black_bars(art_img)
                w_a, h_a = art_img.size
                min_a = min(w_a, h_a)
                art_sq = art_img.crop(((w_a - min_a) // 2, (h_a - min_a) // 2, (w_a + min_a) // 2, (h_a + min_a) // 2))
                art_sq = art_sq.resize((art_size, art_size), Image.Resampling.LANCZOS)
                
                # Mask to rounded square
                art_mask = Image.new("L", (art_size, art_size), 0)
                ImageDraw.Draw(art_mask).rounded_rectangle((0, 0, art_size - 1, art_size - 1), radius=16, fill=255)
                
                # Draw cover art drop shadow
                cover_shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
                cs_draw = ImageDraw.Draw(cover_shadow)
                cs_draw.rounded_rectangle((art_x + 3, art_y + 3, art_x + art_size - 1 + 3, art_y + art_size - 1 + 3), radius=16, fill=(0, 0, 0, 45))
                cover_shadow = cover_shadow.filter(ImageFilter.GaussianBlur(4))
                bg = Image.alpha_composite(bg, cover_shadow)
                draw = ImageDraw.Draw(bg)
                
                bg.paste(art_sq, (art_x, art_y), art_mask)
                
                # Dynamic soft border outline around artwork (Clean white outline)
                draw.rounded_rectangle((art_x, art_y, art_x + art_size - 1, art_y + art_size - 1), radius=16, outline=(255, 255, 255, 160), width=2)
                art_drawn = True
            except Exception as e:
                print(f"Error drawing top song art on wrap card: {e}")
                
        if not art_drawn:
            # Draw beautiful record placeholder shadow
            cover_shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
            cs_draw = ImageDraw.Draw(cover_shadow)
            cs_draw.rounded_rectangle((art_x + 3, art_y + 3, art_x + art_size - 1 + 3, art_y + art_size - 1 + 3), radius=16, fill=(0, 0, 0, 45))
            cover_shadow = cover_shadow.filter(ImageFilter.GaussianBlur(4))
            bg = Image.alpha_composite(bg, cover_shadow)
            draw = ImageDraw.Draw(bg)
            
            # Draw beautiful placeholder rounded square (Solid warm white-pink with border)
            draw.rounded_rectangle(
                (art_x, art_y, art_x + art_size - 1, art_y + art_size - 1),
                radius=16,
                fill=(255, 240, 243, 255),
                outline=(255, 255, 255, 160),
                width=2
            )
            # Center of the artwork tile
            cx, cy = art_x + art_size // 2, art_y + art_size // 2
            # Draw stylized record/vinyl vector in minimalist black/white tones!
            draw.ellipse((cx - 42, cy - 42, cx + 42, cy + 42), fill=(30, 30, 30, 255), outline=(255, 255, 255, 255), width=2)
            # Grooves
            draw.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), outline=(255, 255, 255, 40), width=1)
            draw.ellipse((cx - 20, cy - 20, cx + 20, cy + 20), outline=(255, 255, 255, 40), width=1)
            # Center label
            draw.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=(100, 100, 100, 255))
            # Center hole
            draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(255, 240, 243, 255))
            
        # Clean song title to prevent missing glyph boxes (like Russian/Hindi fonts)
        display_title = clean_unicode_name(title_text)
        if len(display_title) > 34:
            display_title = display_title[:31] + "..."
            
        title_fallbacks = get_fallback_fonts(28)
        draw_text_with_fallback(
            draw,
            (345, art_y + 12),
            display_title,
            (0, 0, 0, 255),
            song_title_font,
            title_fallbacks,
            is_upper=True
        )
        
        # Plays count
        plays_str = f"{play_count} PLAYS"
        plays_fallbacks = get_fallback_fonts(22)
        draw_text_with_fallback(
            draw,
            (345, art_y + 54),
            plays_str,
            (100, 100, 100, 255),
            song_count_font,
            plays_fallbacks,
            is_upper=True
        )
        
    # 7. Symmetrical Footer (Pure solid white with drop shadow for ultimate visibility)
    footer_text = "STORMIFY 26.5  •  YOUR MUSIC, YOUR WAY"
    footer_font = get_font(20, bold=True)
    footer_w = draw.textlength(footer_text, font=footer_font)
    # Footer drop shadow
    draw.text(((1080 - footer_w) // 2 + 1, 1720 + 1), footer_text, fill=(0, 0, 0, 100), font=footer_font)
    draw.text(((1080 - footer_w) // 2, 1720), footer_text, fill=(255, 255, 255, 255), font=footer_font) # Pure White
    
    # 8. Convert and save
    out_path = f"cache/wrapped_{int(time.time())}.jpg"
    bg.convert("RGB").save(out_path, "JPEG", quality=95)
    return out_path


async def download_high_res_thumb(httpx_client, vidid, temp_path):
    # Try high-resolution YouTube thumbnails in priority order to prevent blurred images
    urls_to_try = [
        f"https://i.ytimg.com/vi/{vidid}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{vidid}/hq720.jpg",
        f"https://img.youtube.com/vi/{vidid}/sddefault.jpg",
        f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{vidid}/mqdefault.jpg",
    ]
    for url in urls_to_try:
        try:
            resp = await httpx_client.get(url, timeout=3)
            if resp.status_code == 200:
                with open(temp_path, "wb") as f:
                    f.write(resp.content)
                return True
        except Exception:
            pass
    return False


@app.on_message(filters.command(["wrapped", "mystats"]) & filters.group & ~BANNED_USERS)
async def my_wrapped(client, message: Message):
    user_id = message.from_user.id
    now = time.time()
    if user_id in STATS_LIMIT:
        elapsed = now - STATS_LIMIT[user_id]
        if elapsed < 120:
            remaining = int(120 - elapsed)
            return await message.reply_text(
                f"<blockquote><b>⏳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining} sᴇᴄᴏɴᴅs ʙᴇғᴏʀᴇ ʀᴇ-ɢᴇɴᴇʀᴀᴛɪɴɢ ʏᴏᴜʀ sᴛᴀᴛs.</b></blockquote>"
            )
            
    STATS_LIMIT[user_id] = now
    mystic = await message.reply_text("<blockquote><b>ᴄᴀʟᴄᴜʟᴀᴛɪɴɢ ʏᴏᴜʀ sᴛᴏʀᴍɪғʏ ᴡʀᴀᴘᴘᴇᴅ...</b></blockquote>")
    
    stats = await get_user_stats(user_id)
    if not stats or not stats.get("tracks"):
        return await mystic.edit_text(
            "<blockquote><b>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴘʟᴀʏᴇᴅ ᴀɴʏ sᴏɴɢs ʏᴇᴛ! sᴛᴀʀᴛ ᴘʟᴀʏɪɴɢ sᴏᴍᴇ ᴍᴜsɪᴄ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ʏᴏᴜʀ sᴛᴏʀᴍɪғʏ ᴡʀᴀᴘᴘᴇᴅ sᴛᴀᴛs.</b></blockquote>"
        )
        
    total_played = stats.get("total_played", 0)
    tracks = stats.get("tracks", {})
    
    # Sort tracks by count descending
    sorted_tracks = sorted(tracks.items(), key=lambda x: x[1]["count"], reverse=True)
    
    raw_name = message.from_user.first_name or "User"
    user_name = clean_unicode_name(raw_name)
    if not user_name:
        user_name = "STORMIFY USER"
    try:
        from Opus.utils.database import statsdb
        await statsdb.update_one(
            {"user_id": user_id},
            {"$set": {"user_name": user_name}},
            upsert=True
        )
    except:
        pass
    
    # Download top 5 thumbnails explicitly for the top 5 song artworks (keeps them sharp!)
    top_5_thumbs = {}
    try:
        async with httpx.AsyncClient() as httpx_client:
            tasks = []
            for idx, (vidid, data) in enumerate(sorted_tracks[:5]):
                temp_path = f"cache/top_thumb_{user_id}_{idx}.jpg"
                tasks.append(download_high_res_thumb(httpx_client, vidid, temp_path))
                
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, success in enumerate(responses):
                vidid = sorted_tracks[idx][0]
                temp_path = f"cache/top_thumb_{user_id}_{idx}.jpg"
                if success is True:
                    top_5_thumbs[vidid] = temp_path
                else:
                    top_5_thumbs[vidid] = None
    except Exception as e:
        print(f"Error fetching top 5 thumbs: {e}")
        
    # Prepare top songs for card (passing title, count, and downloaded thumb path!)
    top_songs_list = []
    top_songs_text = ""
    for idx, (vidid, data) in enumerate(sorted_tracks[:5]):
        title = data["title"]
        count = data["count"]
        thumb_path = top_5_thumbs.get(vidid)
        top_songs_list.append((title, count, thumb_path))
        top_songs_text += f"<b>{title[:35]}...</b> [ <code>{count} ᴘʟᴀʏs</code> ]\n"
        
    # Download top 16 thumbnails for the fully packed messy scattered background collage!
    collage_data = []
    try:
        async with httpx.AsyncClient() as httpx_client:
            tasks = []
            # Messy scattered background collage has exactly 16 card slots to completely fill the background!
            for idx, (vidid, data) in enumerate(sorted_tracks[:16]):
                temp_path = f"cache/temp_collage_{user_id}_{idx}.jpg"
                tasks.append(download_high_res_thumb(httpx_client, vidid, temp_path))
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, success in enumerate(responses):
                vidid = sorted_tracks[idx][0]
                data = sorted_tracks[idx][1]
                temp_path = f"cache/temp_collage_{user_id}_{idx}.jpg"
                if success is True:
                    # Save song title, artist/channel, and downloaded thumbnail path
                    collage_data.append((data["title"], "STORMIFY TRACK", temp_path))
    except Exception as e:
        print(f"Error fetching collage: {e}")
        
    # Download avatar
    avatar_path = None
    try:
        photos = [p async for p in client.get_chat_photos(user_id, limit=1)]
        if photos:
            avatar_path = await client.download_media(photos[0].file_id, file_name=f"cache/avatar_{user_id}.jpg")
    except Exception as e:
        print(f"Error fetching avatar: {e}")
        
    # Generate the gorgeous wrapped story card graphic!
    card_path = None
    try:
        card_path = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_wrapped_card(user_name, total_played, top_songs_list, avatar_path, collage_data)
        )
    except Exception as e:
        print(f"Error generating wrapped card: {e}")
    
    # Send the stunning Wrapped card!
    if card_path and os.path.exists(card_path):
        caption = f"<blockquote><b>ᴛʜɪꜱ ɪꜱ ʏᴏᴜʀ ᴜɴɪqᴜᴇ ᴍᴜꜱɪᴄ ᴊᴏᴜʀɴᴇʏ ᴏɴ ꜱᴛᴏʀᴍɪꜰʏ 26.5. ᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴋᴇᴇᴘɪɴɢ ᴛʜᴇ ᴍᴜꜱɪᴄ ᴀʟɪᴠᴇ</b></blockquote>"
        
        await message.reply_photo(
            photo=card_path,
            caption=caption,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Cʟᴏsᴇ", callback_data="close")]])
        )
        await mystic.delete()
    else:
        # Fallback to text mode if image generation failed
        text = f"""<blockquote><b>{user_name}'s STORMIFY Wʀᴀᴘᴘᴇᴅ</b>
 
 <b>Yᴏᴜʀ ᴏᴠᴇʀᴀʟʟ sᴛᴀᴛɪsᴛɪᴄs:</b>
 <b>Tᴏᴛᴀʟ Sᴏɴɢs Pʟᴀʏᴇᴅ:</b> <code>{total_played}</code>
 
 <b>Tᴏᴘ 5 Fᴀᴠᴏʀɪᴛᴇ Tʀᴀᴄᴋs:</b>
 {top_songs_text}
 <i>ᴛʜᴇsᴇ ᴀʀᴇ ᴛʜᴇ ᴛʀᴀᴄᴋs ʏᴏᴜ'ᴠᴇ ʙᴇᴇɴ ᴠɪʙɪɴɢ ᴛᴏ ᴛʜᴇ ᴍᴏsᴛ ᴏɴ Sᴛᴏʀᴍɪғʏ! ᴋᴇᴇᴘ ᴛʜᴇ ᴍᴜsɪᴄ ᴀʟɪᴠᴇ.</i></blockquote>"""

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Cʟᴏsᴇ", callback_data="close")]
        ])

        await mystic.edit_text(text, reply_markup=markup)
        
    # Bulletproof cleanup of all temp files for this specific user to keep cache perfectly pristine
    try:
        for f in glob.glob(f"cache/*_{user_id}*"):
            try:
                os.remove(f)
            except:
                pass
        if card_path and os.path.exists(card_path):
            try:
                os.remove(card_path)
            except:
                pass
    except Exception as e:
        print(f"Error during bulletproof cache cleanup: {e}")


# ==========================================
#          LEADERBOARD CARD GRAPHICS
# ==========================================

def generate_leaderboard_card(period_title, top_user_name, top_user_plays, top_users_list, avatar_path=None, collage_data=None):
    # 1. Create a beautiful base canvas with luxury dark charcoal-rose color
    bg = Image.new("RGB", (1080, 1920), color=(28, 18, 22))
    
    # 2. Render collage
    collage_layer = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    if collage_data:
        positions = [
            (-80, -100, -15),      # 1. Top left
            (200, -140, 8),        # 2. Top center-left
            (500, -120, -10),      # 3. Top center-right
            (800, -60, 12),        # 4. Top right
            (-100, 280, 14),       # 5. Upper left
            (200, 320, -7),        # 6. Upper center-left
            (520, 280, 5),         # 7. Upper center-right
            (830, 350, -12),       # 8. Upper right
            (-80, 680, -10),       # 9. Mid left
            (180, 720, 8),         # 10. Mid center-left
            (500, 660, -5),        # 11. Mid center-right
            (820, 700, 12),        # 12. Mid right
            (-120, 1080, 12),      # 13. Lower-mid left
            (200, 1120, -8),       # 14. Lower-mid center-left
            (520, 1060, 6),        # 15. Lower-mid center-right
            (840, 1100, -14),      # 16. Lower-mid right
            (-60, 1480, -10),      # 17. Bottom left
            (250, 1520, 7),        # 18. Bottom center-left
            (540, 1460, -6),       # 19. Bottom center-right
            (800, 1500, 15),       # 20. Bottom right
        ]
        for idx in range(len(positions)):
            if not collage_data:
                break
            item = collage_data[idx % len(collage_data)]
            title, artist, path = item
            if os.path.exists(path):
                try:
                    card_img = draw_mini_player_card(path, title, artist)
                    px, py, angle = positions[idx]
                    rotated_card = card_img.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
                    orig_w, orig_h = card_img.size
                    rot_w, rot_h = rotated_card.size
                    dx = (rot_w - orig_w) // 2
                    dy = (rot_h - orig_h) // 2
                    collage_layer.paste(rotated_card, (px - dx, py - dy), rotated_card)
                except Exception as e:
                    print(f"Error processing background collage card: {e}")
                    
    bg = Image.alpha_composite(bg.convert("RGBA"), collage_layer)
    overlay = Image.new("RGBA", (1080, 1920), (28, 16, 22, 165))
    bg = Image.alpha_composite(bg, overlay)
    
    glow = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow)
    g_draw.ellipse((100, 100, 980, 980), fill=(255, 182, 193, 28))
    g_draw.ellipse((100, 900, 980, 1780), fill=(255, 182, 193, 20))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    bg = Image.alpha_composite(bg, glow)
    
    draw = ImageDraw.Draw(bg)
    
    # 3. Header Title
    header_text = "S T O R M I F Y   L E A D E R B O A R D"
    header_font = get_font(24, bold=True)
    header_w = draw.textlength(header_text, font=header_font)
    draw.text(((1080 - header_w) // 2 + 2, 80 + 2), header_text, fill=(0, 0, 0, 100), font=header_font)
    draw.text(((1080 - header_w) // 2, 80), header_text, fill=(255, 255, 255, 255), font=header_font)
    
    # Period badge
    period_map = {
        "today": "TODAY",
        "weekly": "WEEKLY",
        "monthly": "MONTHLY",
        "all": "ALL TIME"
    }
    display_period = period_map.get(period_title.lower(), period_title.upper())
    period_str = f"• {display_period} •"
    period_font = get_font(20, bold=True)
    period_w = draw.textlength(period_str, font=period_font)
    draw.text(((1080 - period_w) // 2 + 2, 130 + 2), period_str, fill=(0, 0, 0, 100), font=period_font)
    draw.text(((1080 - period_w) // 2, 130), period_str, fill=(255, 182, 193, 255), font=period_font)
    
    # 4. Top User Avatar
    avatar_y = 190
    avatar_size = 220
    av_x = (1080 - avatar_size) // 2
    avatar_drawn = False
    
    if avatar_path and os.path.exists(avatar_path):
        try:
            av_img = Image.open(avatar_path).convert("RGBA").resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            
            av_shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
            av_s_draw = ImageDraw.Draw(av_shadow)
            av_s_draw.ellipse((av_x + 6, avatar_y + 6, av_x + avatar_size + 6, avatar_y + avatar_size + 6), fill=(0, 0, 0, 60))
            av_shadow = av_shadow.filter(ImageFilter.GaussianBlur(10))
            bg = Image.alpha_composite(bg, av_shadow)
            bg.paste(av_img, (av_x, avatar_y), mask)
            draw = ImageDraw.Draw(bg)
            
            draw.ellipse((av_x - 4, avatar_y - 4, av_x + avatar_size + 4, avatar_y + avatar_size + 4), outline=(255, 255, 255, 255), width=6)
            avatar_drawn = True
        except Exception as e:
            print(f"Error drawing top user avatar on leaderboard card: {e}")
            
    if not avatar_drawn:
        av_shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
        av_s_draw = ImageDraw.Draw(av_shadow)
        av_s_draw.ellipse((av_x + 6, avatar_y + 6, av_x + avatar_size + 6, avatar_y + avatar_size + 6), fill=(0, 0, 0, 60))
        av_shadow = av_shadow.filter(ImageFilter.GaussianBlur(10))
        bg = Image.alpha_composite(bg, av_shadow)
        draw = ImageDraw.Draw(bg)
        
        draw.ellipse((av_x, avatar_y, av_x + avatar_size - 1, avatar_y + avatar_size - 1), fill=(255, 220, 225, 255), outline=(255, 255, 255, 255), width=6)
        cx, cy = av_x + avatar_size // 2, avatar_y + avatar_size // 2
        draw.ellipse((cx - 30, cy - 50, cx + 30, cy + 10), fill=(100, 100, 100, 255))
        draw.ellipse((cx - 50, cy + 20, cx + 50, cy + 70), fill=(100, 100, 100, 255))
        
    # 5. Top User Title
    if has_special_characters(top_user_name):
        name_str = f"{top_user_name}"
    else:
        name_str = f"{top_user_name.upper()}"
        
    name_size = max(32, min(48, int(48 - (len(name_str) - 14) * 1.5))) if len(name_str) > 14 else 48
    name_standard_font = get_font(name_size, bold=True)
    name_fallback_fonts = get_fallback_fonts(name_size)
    
    draw_text_with_fallback(
        draw,
        (0, 440),
        name_str,
        (255, 255, 255, 255),
        name_standard_font,
        name_fallback_fonts,
        shadow_fill=(0, 0, 0, 100),
        center_width=1080
    )
    
    sub_str = "TOP VIBER"
    sub_font = get_font(30, bold=True)
    sub_w = draw.textlength(sub_str, font=sub_font)
    draw.text(((1080 - sub_w) // 2 + 2, 505 + 2), sub_str, fill=(0, 0, 0, 100), font=sub_font)
    draw.text(((1080 - sub_w) // 2, 505), sub_str, fill=(255, 182, 193, 255), font=sub_font)
    
    # 6. Card coordinates
    panel1_x1, panel1_y1 = 110, 580
    panel1_x2, panel1_y2 = 970, 770
    
    panel2_x1, panel2_y1 = 110, 810
    panel2_x2, panel2_y2 = 970, 1660
    
    # Floating shadow layer
    shadow_layer = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_layer)
    s_draw.rounded_rectangle(
        [(panel1_x1 + 8, panel1_y1 + 8), (panel1_x2 + 8, panel1_y2 + 8)],
        radius=32,
        fill=(0, 0, 0, 45)
    )
    s_draw.rounded_rectangle(
        [(panel2_x1 + 8, panel2_y1 + 8), (panel2_x2 + 8, panel2_y2 + 8)],
        radius=32,
        fill=(0, 0, 0, 45)
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(15))
    bg = Image.alpha_composite(bg.convert("RGBA"), shadow_layer)
    
    # Create semi-transparent white panels
    panel_overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(panel_overlay)
    
    p_draw.rounded_rectangle(
        [(panel1_x1, panel1_y1), (panel1_x2, panel1_y2)],
        radius=32,
        fill=(255, 255, 255, 235),
    )
    p_draw.rounded_rectangle(
        [(panel2_x1, panel2_y1), (panel2_x2, panel2_y2)],
        radius=32,
        fill=(255, 255, 255, 235),
    )
    bg = Image.alpha_composite(bg, panel_overlay)
    draw = ImageDraw.Draw(bg)
    
    # Panel 1 Stats Content
    lbl_font = get_font(22, bold=True)
    lbl_text = f"TOP LISTENER'S {display_period} STREAMS"
    lbl_w = draw.textlength(lbl_text, font=lbl_font)
    draw.text(((1080 - lbl_w) // 2, 615), lbl_text, fill=(100, 100, 100, 255), font=lbl_font)
    
    stat_font = get_font(64, bold=True)
    stat_text = str(top_user_plays)
    stat_w = draw.textlength(stat_text, font=stat_font)
    draw.text(((1080 - stat_w) // 2, 655), stat_text, fill=(0, 0, 0, 255), font=stat_font)
    
    # Panel 2 Leaderboard Content
    top_lbl = "TOP CONTENDERS"
    top_lbl_font = get_font(26, bold=True)
    top_lbl_w = draw.textlength(top_lbl, font=top_lbl_font)
    draw.text(((1080 - top_lbl_w) // 2, 850), top_lbl, fill=(0, 0, 0, 255), font=top_lbl_font)
    
    user_name_font = get_font(26, bold=True)
    user_plays_font = get_font(20)
    
    start_y = 930
    y_gap = 135
    
    for idx, user_data in enumerate(top_users_list[:5]):
        u_name, p_count, av_path = user_data
        rank_idx = idx + 2
        
        # Rank Number Badge
        idx_str = str(rank_idx)
        idx_f = get_font(32, bold=True)
        idx_w = draw.textlength(idx_str, font=idx_f)
        draw.text((150 + (30 - idx_w) // 2, start_y + idx * y_gap - 2), idx_str, fill=(0, 0, 0, 255), font=idx_f)
        
        # User Avatar circular cutout
        art_size = 90
        art_x = 220
        art_y = start_y + idx * y_gap - 30
        art_drawn = False
        
        if av_path and os.path.exists(av_path):
            try:
                art_img = Image.open(av_path).convert("RGBA").resize((art_size, art_size), Image.Resampling.LANCZOS)
                art_mask = Image.new("L", (art_size, art_size), 0)
                ImageDraw.Draw(art_mask).ellipse((0, 0, art_size - 1, art_size - 1), fill=255)
                
                cover_shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
                cs_draw = ImageDraw.Draw(cover_shadow)
                cs_draw.ellipse((art_x + 3, art_y + 3, art_x + art_size - 1 + 3, art_y + art_size - 1 + 3), fill=(0, 0, 0, 45))
                cover_shadow = cover_shadow.filter(ImageFilter.GaussianBlur(4))
                bg = Image.alpha_composite(bg, cover_shadow)
                draw = ImageDraw.Draw(bg)
                
                bg.paste(art_img, (art_x, art_y), art_mask)
                draw.ellipse((art_x, art_y, art_x + art_size - 1, art_y + art_size - 1), outline=(255, 255, 255, 255), width=2)
                art_drawn = True
            except Exception as e:
                print(f"Error drawing user avatar on leaderboard card: {e}")
                
        if not art_drawn:
            cover_shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
            cs_draw = ImageDraw.Draw(cover_shadow)
            cs_draw.ellipse((art_x + 3, art_y + 3, art_x + art_size - 1 + 3, art_y + art_size - 1 + 3), fill=(0, 0, 0, 45))
            cover_shadow = cover_shadow.filter(ImageFilter.GaussianBlur(4))
            bg = Image.alpha_composite(bg, cover_shadow)
            draw = ImageDraw.Draw(bg)
            
            draw.ellipse((art_x, art_y, art_x + art_size - 1, art_y + art_size - 1), fill=(255, 220, 225, 255), outline=(255, 255, 255, 255), width=2)
            cx, cy = art_x + art_size // 2, art_y + art_size // 2
            draw.ellipse((cx - 15, cy - 25, cx + 15, cy + 5), fill=(100, 100, 100, 255))
            draw.ellipse((cx - 24, cy + 10, cx + 24, cy + 35), fill=(100, 100, 100, 255))
            
        display_name = clean_unicode_name(u_name)
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
            
        name_fallbacks = get_fallback_fonts(26)
        draw_text_with_fallback(
            draw,
            (345, art_y + 8),
            display_name,
            (0, 0, 0, 255),
            user_name_font,
            name_fallbacks,
            is_upper=True
        )
        
        plays_str = f"{p_count} PLAYS"
        plays_fallbacks = get_fallback_fonts(20)
        draw_text_with_fallback(
            draw,
            (345, art_y + 46),
            plays_str,
            (100, 100, 100, 255),
            user_plays_font,
            plays_fallbacks,
            is_upper=True
        )
        
    # 7. Symmetrical Footer
    footer_text = "STORMIFY 26.5  •  TOP LISTENERS LEADERBOARD"
    footer_font = get_font(20, bold=True)
    footer_w = draw.textlength(footer_text, font=footer_font)
    draw.text(((1080 - footer_w) // 2 + 1, 1720 + 1), footer_text, fill=(0, 0, 0, 100), font=footer_font)
    draw.text(((1080 - footer_w) // 2, 1720), footer_text, fill=(255, 255, 255, 255), font=footer_font)
    
    # 8. Convert and save
    out_path = f"cache/leaderboard_{period_title}_{int(time.time())}.jpg"
    bg.convert("RGB").save(out_path, "JPEG", quality=95)
    return out_path


# ==========================================
#         LEADERBOARD CORE LOGIC / APIS
# ==========================================

async def process_leaderboard_request(client, period, chat_id, user_id):
    """
    Dry, highly robust implementation of leaderboard generation.
    Returns: (card_path, downloaded_files) or error string
    """
    # 1. Check global leaderboard image cache to minimize CPU & Network overhead
    now_time = time.time()
    cached = LEADERBOARD_CACHE.get(period)
    if cached:
        cached_path = cached.get("card_path")
        timestamp = cached.get("timestamp")
        if now_time - timestamp < LEADERBOARD_CACHE_EXPIRY and cached_path and os.path.exists(cached_path):
            temp_path = f"cache/leaderboard_temp_{period}_{int(now_time)}.jpg"
            try:
                shutil.copy(cached_path, temp_path)
                return temp_path, []
            except Exception as e:
                print(f"Error copying cached leaderboard image: {e}")

    leaderboard = await get_leaderboard(period, limit=6)
    if not leaderboard:
        return f"<blockquote><b>ɴᴏ ᴘʟᴀʏ ꜱᴛᴀᴛꜱ ʀᴇᴄᴏʀᴅᴇᴅ ʏᴇᴛ ꜰᴏʀ ᴛʜɪꜱ ᴘᴇʀɪᴏᴅ! ꜱᴛᴀʀᴛ ᴘʟᴀʏɪɴɢ ꜱᴏᴍᴇ ᴍᴜꜱɪᴄ ᴛᴏ ʙᴜɪʟᴅ ᴛʜᴇ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ.</b></blockquote>"
        
    downloaded_files = []
    now_ts = int(time.time())
    
    # Securely resolve userbot assistant client for the group chat to bypass bot API restrictions
    try:
        from Opus.utils.database import get_assistant_number, get_client
        ass_num = await get_assistant_number(chat_id)
        assistant_client = await get_client(ass_num) if ass_num else None
    except Exception:
        assistant_client = None
        
    if not assistant_client:
        assistant_client = client
        
    # Pre-fetch and cache group members in one swift pass to populate Pyrogram's peer database and fetch names!
    group_members_cache = {}
    try:
        async for member in client.get_chat_members(chat_id, limit=200):
            if member and member.user:
                group_members_cache[member.user.id] = member.user
    except Exception:
        pass
        
    if assistant_client != client:
        try:
            async for member in assistant_client.get_chat_members(chat_id, limit=200):
                if member and member.user:
                    group_members_cache[member.user.id] = member.user
        except Exception:
            pass
            
    # Also fetch recent group chat history to resolve peers of active contenders!
    try:
        async for msg in client.get_chat_history(chat_id, limit=100):
            if msg.from_user:
                group_members_cache[msg.from_user.id] = msg.from_user
    except Exception:
        pass
            
    # Live database self-healing background cache population!
    from Opus.utils.database import statsdb
    for uid, u_obj in group_members_cache.items():
        if u_obj and u_obj.first_name:
            try:
                asyncio.create_task(statsdb.update_one(
                    {"user_id": uid},
                    {"$set": {"user_name": clean_unicode_name(u_obj.first_name)}},
                    upsert=False
                ))
            except:
                pass
        
    # Resolve all user objects in parallel safely using the cached participants, get_chat, get_chat_member, or get_users
    async def fetch_user_safe(uid):
        if uid in group_members_cache:
            return group_members_cache[uid]
        # 1. Try resolving using client.get_chat which fetches user chat directly from Telegram servers!
        try:
            chat_obj = await client.get_chat(uid)
            if chat_obj:
                return chat_obj
        except Exception:
            pass
        if assistant_client != client:
            try:
                chat_obj = await assistant_client.get_chat(uid)
                if chat_obj:
                    return chat_obj
            except Exception:
                pass
        # 2. Try get_chat_member via the assistant client
        if assistant_client != client:
            try:
                member = await assistant_client.get_chat_member(chat_id, uid)
                if member and member.user:
                    return member.user
            except Exception:
                pass
                
        # 3. Try get_chat_member via the main bot client
        try:
            member = await client.get_chat_member(chat_id, uid)
            if member and member.user:
                return member.user
        except Exception:
            pass
            
        # 4. Try get_users via the assistant client
        if assistant_client != client:
            try:
                return await assistant_client.get_users(uid)
            except Exception:
                pass
                
        # 5. Try get_users via the main bot client
        try:
            return await client.get_users(uid)
        except Exception:
            return None

    user_ids = [int(u["user_id"]) for u in leaderboard[:6]]
    resolved_list = await asyncio.gather(*[fetch_user_safe(uid) for uid in user_ids])
    users_info = {}
    for i, uid in enumerate(user_ids):
        if i < len(resolved_list) and resolved_list[i]:
            users_info[uid] = resolved_list[i]
            
    # Download avatars directly via small_file_id or get_chat_photos query directly
    async def download_avatar_safe(uid):
        user_obj = users_info.get(uid)
        # Attempt 1: Download directly via resolved small_file_id using bot client
        if user_obj and user_obj.photo:
            try:
                dest = f"cache/avatar_lb_{uid}_{now_ts}.jpg"
                path = await client.download_media(user_obj.photo.small_file_id, file_name=dest)
                if path:
                    return path
            except Exception:
                pass
            # Attempt 2: Download directly via resolved small_file_id using assistant client
            if assistant_client != client:
                try:
                    dest = f"cache/avatar_lb_{uid}_{now_ts}.jpg"
                    path = await assistant_client.download_media(user_obj.photo.small_file_id, file_name=dest)
                    if path:
                        return path
                except Exception:
                    pass
        # Attempt 3: Query profile photos directly using main bot client (exactly like my_wrapped / mystats!)
        try:
            photos = [p async for p in client.get_chat_photos(uid, limit=1)]
            if photos:
                dest = f"cache/avatar_lb_{uid}_{now_ts}.jpg"
                path = await client.download_media(photos[0].file_id, file_name=dest)
                if path:
                    return path
        except Exception:
            pass
        # Attempt 4: Query profile photos directly using assistant client
        if assistant_client != client:
            try:
                photos = [p async for p in assistant_client.get_chat_photos(uid, limit=1)]
                if photos:
                    dest = f"cache/avatar_lb_{uid}_{now_ts}.jpg"
                    path = await assistant_client.download_media(photos[0].file_id, file_name=dest)
                    if path:
                        return path
            except Exception:
                pass
        return None

    avatar_paths_list = await asyncio.gather(*[download_avatar_safe(uid) for uid in user_ids])
    user_avatars = {}
    for i, uid in enumerate(user_ids):
        if i < len(avatar_paths_list) and avatar_paths_list[i]:
            user_avatars[uid] = avatar_paths_list[i]
            downloaded_files.append(avatar_paths_list[i])
            
    # Create the packed background collage using tracks of the top users
    top_user_id = int(leaderboard[0]["user_id"])
    top_user_stats = await get_user_stats(top_user_id)
    top_user_tracks = top_user_stats.get("tracks", {}) if top_user_stats else {}
    sorted_top_user_tracks = sorted(top_user_tracks.items(), key=lambda x: x[1]["count"], reverse=True)
    
    all_tracks_pool = []
    for vidid, tdata in sorted_top_user_tracks:
        all_tracks_pool.append((vidid, tdata))
        
    # If the top user has fewer than 20 tracks, fill the remaining collage slots with other users' tracks!
    if len(all_tracks_pool) < 20:
        for u_data in leaderboard[1:6]:
            u_stats = await get_user_stats(u_data["user_id"])
            if u_stats and u_stats.get("tracks"):
                u_tracks = sorted(u_stats["tracks"].items(), key=lambda x: x[1]["count"], reverse=True)
                for vidid, tdata in u_tracks:
                    if vidid not in [x[0] for x in all_tracks_pool]:
                        all_tracks_pool.append((vidid, tdata))
                    if len(all_tracks_pool) >= 20:
                        break
            if len(all_tracks_pool) >= 20:
                break
                
    # Download top 20 thumbnails for collage in parallel
    collage_data = []
    try:
        async with httpx.AsyncClient() as httpx_client:
            tasks = []
            for idx, (vidid, tdata) in enumerate(all_tracks_pool[:20]):
                temp_path = f"cache/lb_collage_{top_user_id}_{idx}_{now_ts}.jpg"
                tasks.append(download_high_res_thumb(httpx_client, vidid, temp_path))
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, success in enumerate(responses):
                if idx < len(all_tracks_pool):
                    vidid, tdata = all_tracks_pool[idx]
                    temp_path = f"cache/lb_collage_{top_user_id}_{idx}_{now_ts}.jpg"
                    if success is True:
                        collage_data.append((tdata["title"], "STORMIFY TRACK", temp_path))
                        downloaded_files.append(temp_path)
    except Exception as e:
        print(f"Error fetching leaderboard collage: {e}")
        
    # Prepare data for generation
    top_user_name = None
    if top_user_stats:
        top_user_name = top_user_stats.get("user_name")
        
    if not top_user_name:
        top_user_obj = users_info.get(top_user_id)
        top_user_name = top_user_obj.first_name if top_user_obj and top_user_obj.first_name else str(top_user_id)
        
    top_user_plays = leaderboard[0]["period_plays"]
    top_user_avatar = user_avatars.get(top_user_id)
    
    other_users_list = []
    for u_data in leaderboard[1:6]:
        uid = int(u_data["user_id"])
        plays = u_data["period_plays"]
        
        # Try database first for maximum caching coverage
        u_name = None
        u_stats = await get_user_stats(uid)
        if u_stats:
            u_name = u_stats.get("user_name")
            
        if not u_name:
            u_obj = users_info.get(uid)
            u_name = u_obj.first_name if u_obj and u_obj.first_name else str(uid)
            
        u_avatar = user_avatars.get(uid)
        other_users_list.append((u_name, plays, u_avatar))
        
    card_path = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: generate_leaderboard_card(
            period_title=period,
            top_user_name=top_user_name,
            top_user_plays=top_user_plays,
            top_users_list=other_users_list,
            avatar_path=top_user_avatar,
            collage_data=collage_data
        )
    )
    
    # 2. Update global cache with a permanent copy for subsequent O(1) requests
    if card_path and os.path.exists(card_path):
        try:
            cache_path = f"cache/leaderboard_cached_{period}.jpg"
            shutil.copy(card_path, cache_path)
            LEADERBOARD_CACHE[period] = {
                "card_path": cache_path,
                "timestamp": now_time
            }
        except Exception as e:
            print(f"Error saving to leaderboard cache: {e}")

    return card_path, downloaded_files


def get_leaderboard_buttons(active_period):
    def get_btn(text, period):
        btn_text = f"• {text} •" if active_period == period else text
        return InlineKeyboardButton(btn_text, callback_data=f"leaderboard_{period}")
        
    markup = InlineKeyboardMarkup([
        [
            get_btn("ᴛᴏᴅᴀʏ", "today"),
            get_btn("ᴡᴇᴇᴋʟʏ", "weekly")
        ],
        [
            get_btn("ᴍᴏɴᴛʜʟʏ", "monthly"),
            get_btn("ᴀʟʟ", "all")
        ],
        [
            InlineKeyboardButton("🗑 Cʟᴏsᴇ", callback_data="close")
        ]
    ])
    return markup


@app.on_message(filters.command(["leaderboard", "leaders"]) & filters.group & ~BANNED_USERS)
async def leaderboard_cmd(client, message: Message):
    user_id = message.from_user.id
    now = time.time()
    if user_id in LEADERBOARD_LIMIT:
        elapsed = now - LEADERBOARD_LIMIT[user_id]
        if elapsed < 120:
            remaining = int(120 - elapsed)
            return await message.reply_text(
                f"<blockquote><b>⏳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining} sᴇᴄᴏɴᴅs ʙᴇғᴏʀᴇ ʀᴇ-ɢᴇɴᴇʀᴀᴛɪɴɢ ᴛʜᴇ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ.</b></blockquote>"
            )
            
    LEADERBOARD_LIMIT[user_id] = now
    args = message.text.split()
    period = "all"
    if len(args) > 1:
        arg = args[1].lower()
        if arg in ["today", "daily", "day"]:
            period = "today"
        elif arg in ["weekly", "week"]:
            period = "weekly"
        elif arg in ["monthly", "month"]:
            period = "monthly"
        elif arg in ["all", "alltime"]:
            period = "all"
            
    mystic = await message.reply_text(f"<blockquote><b>ᴄᴀʟᴄᴜʟᴀᴛɪɴɢ sᴛᴏʀᴍɪғʏ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ ({period.upper()})...</b></blockquote>")
    
    card_path = None
    downloaded_files = []
    try:
        # Cache caller's name immediately in statsdb
        try:
            from Opus.utils.database import statsdb
            await statsdb.update_one(
                {"user_id": message.from_user.id},
                {"$set": {"user_name": clean_unicode_name(message.from_user.first_name or "User")}},
                upsert=True
            )
        except:
            pass
            
        res = await process_leaderboard_request(client, period, message.chat.id, message.from_user.id)
        if isinstance(res, tuple):
            card_path, downloaded_files = res
        else:
            await mystic.delete()
            return await message.reply_text(res)
            
        if card_path and os.path.exists(card_path):
            caption = f"<blockquote><b>🏆 ꜱᴛᴏʀᴍɪꜰʏ ᴍᴜꜱɪᴄ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ ({period.upper()}) ɪꜱ ʜᴇʀᴇ! ᴛʜᴇꜱᴇ ᴀʀᴇ ᴛʜᴇ ᴛᴏᴘ ᴠɪʙᴇʀꜱ ᴋᴇᴇᴘɪɴɢ ᴛʜᴇ ᴍᴜꜱɪᴄ ᴀʟɪᴠᴇ.</b></blockquote>"
            await message.reply_photo(
                photo=card_path,
                caption=caption,
                reply_markup=get_leaderboard_buttons(period)
            )
            await mystic.delete()
        else:
            await mystic.edit_text("<blockquote><b>ꜰᴀɪʟᴇᴅ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ ᴄᴀʀᴅ. ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b></blockquote>")
    except Exception as e:
        print(f"Error in leaderboard_cmd: {e}")
        await mystic.edit_text(f"<blockquote><b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ:</b> <code>{str(e)}</code></blockquote>")
    finally:
        # Dry cleanup of temporary files
        for f in downloaded_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        if card_path and os.path.exists(card_path):
            try:
                os.remove(card_path)
            except:
                pass


@app.on_callback_query(filters.regex(r"^leaderboard_(today|weekly|monthly|all)$") & ~BANNED_USERS)
async def leaderboard_callback(client, query):
    user_id = query.from_user.id
    now = time.time()
    if user_id in LEADERBOARD_LIMIT:
        elapsed = now - LEADERBOARD_LIMIT[user_id]
        if elapsed < 120:
            remaining = int(120 - elapsed)
            return await query.answer(
                f"⏳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining}s ʙᴇғᴏʀᴇ sᴡɪᴛᴄʜɪɴɢ ᴄᴀᴛᴇɢᴏʀɪᴇs.",
                show_alert=True
            )
            
    LEADERBOARD_LIMIT[user_id] = now
    period = query.data.split("_")[1]
    
    card_path = None
    downloaded_files = []
    try:
        # Cache caller's name immediately in statsdb
        try:
            from Opus.utils.database import statsdb
            await statsdb.update_one(
                {"user_id": query.from_user.id},
                {"$set": {"user_name": clean_unicode_name(query.from_user.first_name or "User")}},
                upsert=True
            )
        except:
            pass
            
        res = await process_leaderboard_request(client, period, query.message.chat.id, query.from_user.id)
        if isinstance(res, tuple):
            card_path, downloaded_files = res
        else:
            return await query.answer(res.replace("<blockquote>", "").replace("</blockquote>", "").replace("<b>", "").replace("</b>", ""), show_alert=True)
            
        if card_path and os.path.exists(card_path):
            caption = f"<blockquote><b>🏆 ꜱᴛᴏʀᴍɪꜰʏ ᴍᴜꜱɪᴄ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ ({period.upper()}) ɪꜱ ʜᴇʀᴇ! ᴛʜᴇꜱᴇ ᴀʀᴇ ᴛʜᴇ ᴛᴏᴘ ᴠɪʙᴇʀꜱ ᴋᴇᴇᴘɪɴɢ ᴛʜᴇ ᴍᴜꜱɪᴄ ᴀʟɪᴠᴇ.</b></blockquote>"
            await client.edit_message_media(
                chat_id=query.message.chat.id,
                message_id=query.message.id,
                media=InputMediaPhoto(card_path, caption=caption),
                reply_markup=get_leaderboard_buttons(period)
            )
            try:
                await query.answer()
            except:
                pass
    except Exception as e:
        print(f"Error in leaderboard_callback: {e}")
        try:
            await query.answer(f"Error: {str(e)}", show_alert=True)
        except:
            pass
    finally:
        for f in downloaded_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        if card_path and os.path.exists(card_path):
            try:
                os.remove(card_path)
            except:
                pass
