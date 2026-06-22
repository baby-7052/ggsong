import os
import asyncio
import re
import aiofiles
import aiohttp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance, ImageFilter
from youtubesearchpython.future import VideosSearch
import config
from config import FAILED, SPOTIFY_PLAYLIST_IMG_URL
from unidecode import unidecode
import unicodedata

APPLE_TEMPLATE_PATH = "Opus/assets/apple_music.png"

def _resample_lanczos():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.ANTIALIAS

def safe_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def _most_common_colors(pil_img, n=3, resize=(64, 64)):
    im = pil_img.convert("RGB").resize(resize)
    arr = np.array(im).reshape(-1, 3)
    quant = (arr >> 3) << 3
    tuples = [tuple(c) for c in quant.tolist()]
    unique, counts = np.unique(tuples, axis=0, return_counts=True)
    idx = np.argsort(counts)[::-1]
    colors = [tuple(map(int, unique[i])) for i in idx[:n]]
    return colors or [(120, 120, 120)]

def get_contrasting_color(bg_color):
    lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
    return (30, 30, 30) if lum > 128 else (245, 245, 245)

def remove_black_bars(img, tolerance=15):
    try:
        # Convert image to grayscale to analyze brightness
        gray = img.convert("L")
        arr = np.array(gray)
        h, w = arr.shape
        
        # Scan from top down to 25% of height, and bottom up to 25% of height
        top_limit = int(h * 0.25)
        bottom_limit = int(h * 0.75)
        
        top_crop = 0
        for r in range(top_limit):
            if np.mean(arr[r, :]) < tolerance:
                top_crop = r + 1
            else:
                break
                
        bottom_crop = h
        for r in range(h - 1, bottom_limit, -1):
            if np.mean(arr[r, :]) < tolerance:
                bottom_crop = r
            else:
                break
                
        # Also check for left and right black bars
        left_limit = int(w * 0.25)
        right_limit = int(w * 0.75)
        
        left_crop = 0
        for c in range(left_limit):
            if np.mean(arr[:, c]) < tolerance:
                left_crop = c + 1
            else:
                break
                
        right_crop = w
        for c in range(w - 1, right_limit, -1):
            if np.mean(arr[:, c]) < tolerance:
                right_crop = c
            else:
                break
                
        if (right_crop - left_crop) > w * 0.5 and (bottom_crop - top_crop) > h * 0.5:
            return img.crop((left_crop, top_crop, right_crop, bottom_crop))
    except Exception as e:
        print(f"Error removing black bars: {e}")
    return img

def _detect_panel_bounds(img_rgba):
    W, H = img_rgba.size
    gray = img_rgba.convert("L")
    arr = np.array(gray)

    thr = int(np.percentile(arr, 90))
    mask = (arr >= thr).astype(np.uint8)

    y0 = int(H * 0.25)
    y1 = int(H * 0.75)
    band = mask[y0:y1, :]

    visited = np.zeros_like(band, dtype=np.uint8)
    best = None
    h, w = band.shape

    def neighbors(r, c):
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                yield rr, cc

    for r in range(h):
        for c in range(w):
            if band[r, c] and not visited[r, c]:
                stack = [(r, c)]
                visited[r, c] = 1
                min_r = max_r = r
                min_c = max_c = c
                area = 0
                while stack:
                    rr, cc = stack.pop()
                    area += 1
                    min_r = min(min_r, rr)
                    max_r = max(max_r, rr)
                    min_c = min(min_c, cc)
                    max_c = max(max_c, cc)
                    for nr, nc in neighbors(rr, cc):
                        if band[nr, nc] and not visited[nr, nc]:
                            visited[nr, nc] = 1
                            stack.append((nr, nc))
                comp_x_center = (min_c + max_c) / 2
                if best is None or (area > best[0] and comp_x_center > w * 0.5):
                    X0, X1 = min_c, max_c
                    Y0, Y1 = y0 + min_r, y0 + max_r
                    best = (area, X0, X1, Y0, Y1)

    if best is None:
        panel_w = int(W * 0.68)
        panel_h = int(H * 0.36)
        panel_x0 = (W - panel_w) // 2
        panel_x1 = panel_x0 + panel_w
        panel_y0 = (H - panel_h) // 2
        panel_y1 = panel_y0 + panel_h
        return panel_x0, panel_x1, panel_y0, panel_y1

    _, px0, px1, py0, py1 = best
    pad_y = int(H * 0.05)
    py0 = max(0, py0 - pad_y)
    py1 = min(H - 1, py1 + pad_y)
    return px0, px1, py0, py1

def _detect_left_card_bounds(img_rgba):
    W, H = img_rgba.size
    gray = img_rgba.convert("L")
    arr = np.array(gray)

    x_band = int(W * 0.28)
    sub = arr[:, :x_band]

    thr = int(np.percentile(sub, 88))
    mask = (sub >= thr).astype(np.uint8)

    visited = np.zeros_like(mask, dtype=np.uint8)
    best = None
    h, w = mask.shape

    def neighbors(r, c):
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w:
                yield rr, cc

    for r in range(h):
        for c in range(w):
            if mask[r, c] and not visited[r, c]:
                stack = [(r, c)]
                visited[r, c] = 1
                min_r = max_r = r
                min_c = max_c = c
                area = 0
                while stack:
                    rr, cc = stack.pop()
                    area += 1
                    min_r = min(min_r, rr)
                    max_r = max(max_r, rr)
                    min_c = min(min_c, c)
                    max_c = max(max_c, c)
                    for nr, nc in neighbors(rr, cc):
                        if mask[nr, nc] and not visited[nr, nc]:
                            visited[nr, nc] = 1
                            stack.append((nr, nc))
                comp_h = max_r - min_r + 1
                comp_w = max_c - min_c + 1
                if comp_h > comp_w and (best is None or area > best[0]):
                    X0, X1 = min_c, max_c
                    Y0, Y1 = min_r, max_r
                    best = (area, X0, X1, Y0, Y1)

    if best is None:
        card_w = int(W * 0.08)
        card_h = int(H * 0.36)
        x0 = int(W * 0.04)
        x1 = x0 + card_w
        y0 = (H - card_h) // 2
        y1 = y0 + card_h
        return x0, x1, y0, y1

    _, lx0, lx1, ly0, ly1 = best
    return lx0, lx1, ly0, ly1

async def get_thumb(videoid, force_url=None, force_title=None, chat_id=None):
    from Opus.utils.database import get_thumb_style, get_thumb_align
    
    style = 1
    align = "center"
    if chat_id:
        try:
            style = await get_thumb_style(chat_id)
            align = await get_thumb_align(chat_id)
        except Exception as e:
            print(f"Error getting thumb style/align: {e}")
            
    final_path = f"cache/{videoid}_style{style}_{align}.png"
    if os.path.isfile(final_path):
        return final_path

    try:
        if force_url:
            thumbnail_url = force_url
            title = force_title or "Unknown Title"
            channel = "Track"
        elif any(x in videoid for x in ["vortex_", "spotify", "apple", "index"]):
            # Fallback to default images for non-YouTube tracks if no force_url is provided
            if "apple" in videoid:
                thumbnail_url = config.APPLE_TEMPLATE_PATH # We'll use this as fallback
            else:
                thumbnail_url = config.SPOTIFY_PLAYLIST_IMG_URL
            title = force_title or "Streaming Track"
            channel = "Playlist"
        else:
            # Use direct YouTube thumbnail URL — no API call needed!
            thumbnail_url = f"https://i.ytimg.com/vi/{videoid}/maxresdefault.jpg"
            title = force_title or "Unknown Title"
            channel = "YouTube"
        
        # Transliterate title and channel to English for thumbnail rendering
        title = unidecode(unicodedata.normalize('NFKD', str(title)))
        channel = unidecode(unicodedata.normalize('NFKD', str(channel)))

        os.makedirs("cache", exist_ok=True)
        raw_path = f"cache/raw_{videoid}.jpg"

        # Retry/fallback logic for thumbnail download to always fetch the highest quality available
        urls_to_try = []
        is_youtube = not any(x in videoid for x in ["vortex_", "spotify", "apple", "index"])
        
        # If it's a YouTube track, prioritize ultra-HD YouTube URLs first (since force_url from search APIs is usually low-res 360p)
        if is_youtube:
            urls_to_try.extend([
                f"https://i.ytimg.com/vi/{videoid}/maxresdefault.jpg",
                f"https://img.youtube.com/vi/{videoid}/hq720.jpg",
                f"https://img.youtube.com/vi/{videoid}/sddefault.jpg",
            ])
            
        # Append the force_url (either Spotify high-res art, or YouTube search fallback)
        if force_url:
            urls_to_try.append(force_url)
            
        # Add lower-resolution YouTube fallbacks at the end
        if is_youtube:
            urls_to_try.extend([
                f"https://img.youtube.com/vi/{videoid}/hqdefault.jpg",
                f"https://img.youtube.com/vi/{videoid}/mqdefault.jpg",
            ])
            
        # Ensure we always have fallback Spotify/Playlist URLs if needed
        if not is_youtube:
            if "apple" in videoid:
                urls_to_try.append(config.APPLE_TEMPLATE_PATH)
            urls_to_try.append(config.SPOTIFY_PLAYLIST_IMG_URL)
            
        # De-duplicate while preserving order
        seen = set()
        urls_to_try = [x for x in urls_to_try if not (x in seen or seen.add(x))]

        success = False
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        for url in urls_to_try:
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, timeout=8) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            async with aiofiles.open(raw_path, "wb") as f:
                                await f.write(content)
                            success = True
                            break
            except Exception as e:
                print(f"[get_thumb download try failed for {url}] {e}")
                
        if not success:
            # Generate a gorgeous placeholder gradient cover image dynamically!
            try:
                src = Image.new("RGBA", (380, 380), (30, 20, 40, 255))
                draw_placeholder = ImageDraw.Draw(src)
                draw_placeholder.ellipse([80, 80, 300, 300], fill=(255, 45, 85, 40))
                draw_placeholder.ellipse([0, 200, 200, 380], fill=(0, 122, 255, 30))
                
                font_placeholder = safe_font("Opus/assets/font.ttf", 36)
                draw_placeholder.text((110, 165), "Stormify", fill=(255, 255, 255, 180), font=font_placeholder)
                success = True
            except Exception as e:
                print(f"Failed to generate dynamic placeholder cover: {e}")
                return FAILED

        if success and 'src' not in locals():
            try:
                src = Image.open(raw_path).convert("RGBA")
            except Exception as e:
                print(f"Error opening raw image: {e}")
                return FAILED
            
        # Dimensions for thumbnail
        W, H = 1280, 720
        
        def ellipsize(s, font, max_w):
            temp_img = Image.new("RGBA", (10, 10))
            temp_draw = ImageDraw.Draw(temp_img)
            if temp_draw.textbbox((0, 0), s, font=font)[2] <= max_w: return s
            lo, hi = 1, len(s)
            best = "…"
            while lo <= hi:
                mid = (lo + hi) // 2
                cand = s[:mid].rstrip() + "…"
                if temp_draw.textbbox((0, 0), cand, font=font)[2] <= max_w:
                    best = cand
                    lo = mid + 1
                else:
                    hi = mid - 1
            return best

        if style == 2:
            # ----------------- STYLE 2: Apple Music centered Now Playing Theme (Pristine 1080p Resolution) -----------------
            W, H = 1920, 1080
            
            # Remove black bars and crop a perfect center square from the artwork
            src_clean = remove_black_bars(src)
            w_c, h_c = src_clean.size
            if w_c > h_c:
                offset = (w_c - h_c) // 2
                src_square = src_clean.crop((offset, 0, offset + h_c, h_c))
            else:
                offset = (h_c - w_c) // 2
                src_square = src_clean.crop((0, offset, w_c, offset + w_c))

            # 1. Clean dynamic blurred matching background
            bg = src_square.resize((W, H), Image.Resampling.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(100))
            
            # Dark glassy overlay for excellent readability and design aesthetic
            bg_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 110))
            bg = Image.alpha_composite(bg, bg_overlay)

            # 2. Card Dimensions (exactly square, rounded, drop shadow)
            card_w = 570
            card_x = (W - card_w) // 2
            card_y = 165
            cover_radius = 15  # 15px radius at 1080p is equivalent to 10px radius at 720p
            
            # Card drop shadow (reduced opacity, blur, and size for a soft, realistic effect)
            shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw_shadow = ImageDraw.Draw(shadow)
            draw_shadow.rounded_rectangle(
                (card_x - 9, card_y - 9, card_x + card_w + 8, card_y + card_w + 8),
                radius=cover_radius + 9,
                fill=(0, 0, 0, 75)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(18))
            bg = Image.alpha_composite(bg, shadow)
            
            # Paste cover art
            cover_resized = src_square.resize((card_w, card_w), Image.Resampling.LANCZOS)
            cover_mask = Image.new("L", (card_w, card_w), 0)
            ImageDraw.Draw(cover_mask).rounded_rectangle((0, 0, card_w - 1, card_w - 1), radius=cover_radius, fill=255)
            bg.paste(cover_resized, (card_x, card_y), cover_mask)
            
            # Initialize drawing helper (white outline border removed)
            draw = ImageDraw.Draw(bg)
            
            # 3. Add Song Title & Subtitle Left-Aligned with right-aligned icons
            title_font = safe_font("Opus/assets/font.ttf", 37)
            artist_font = safe_font("Opus/assets/font2.ttf", 26)
            
            title_draw = ellipsize(title, title_font, 390)
            artist_draw = ellipsize(channel, artist_font, 540)
            
            title_y = card_y + card_w + 52
            draw.text((card_x, title_y), title_draw, fill=(255, 255, 255, 255), font=title_font)
            
            artist_y = title_y + 45
            artist_album_text = "Stormify 26.5"
            draw.text((card_x, artist_y), artist_album_text, fill=(255, 255, 255, 140), font=artist_font)
            
            # Draw ☆ and ••• icons right-aligned with the right side of the card
            icons_text = "☆   ⋯"
            icons_font = safe_font("Opus/assets/font.ttf", 30)
            icons_w = draw.textbbox((0, 0), icons_text, font=icons_font)[2]
            icons_x = card_x + card_w - icons_w
            icons_y = title_y - 3
            draw.text((icons_x, icons_y), icons_text, fill=(255, 255, 255, 220), font=icons_font)
            
            # 4. Progress Scrubber Bar
            bar_w = card_w
            bar_x = card_x
            bar_y = artist_y + 82
            bar_h = 7
            
            # Background track
            draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=3, fill=(255, 255, 255, 45))
            # Filled track (~32% complete)
            active_w = int(bar_w * 0.32)
            draw.rounded_rectangle((bar_x, bar_y, bar_x + active_w, bar_y + bar_h), radius=3, fill=(255, 255, 255, 255))
            
            # Scrubber Time Labels under scrubber line
            time_font = safe_font("Opus/assets/font2.ttf", 18)
            draw.text((bar_x, bar_y + 18), "0:59", fill=(255, 255, 255, 140), font=time_font)
            total_str = "3:39"
            total_w = draw.textbbox((0, 0), total_str, font=time_font)[2]
            draw.text((bar_x + bar_w - total_w, bar_y + 18), total_str, fill=(255, 255, 255, 140), font=time_font)
            
            # 5. Playback Controls Centered at the Bottom W // 2 = 960
            center_x = W // 2
            controls_y = bar_y + 63
            controls_cy = controls_y + 18
            
            sh_cx = center_x - 210
            pr_cx = center_x - 98
            pa_cx = center_x
            ne_cx = center_x + 98
            rp_cx = center_x + 210
            
            # Shuffle icon (two elegant crossing curved arrows)
            draw.line([(sh_cx - 18, controls_cy - 8), (sh_cx - 6, controls_cy - 8), (sh_cx + 6, controls_cy + 8), (sh_cx + 18, controls_cy + 8)], fill=(255, 255, 255, 140), width=3)
            draw.line([(sh_cx - 18, controls_cy + 8), (sh_cx - 6, controls_cy + 8), (sh_cx + 6, controls_cy - 8), (sh_cx + 18, controls_cy - 8)], fill=(255, 255, 255, 140), width=3)
            draw.polygon([(sh_cx + 18, controls_cy + 8), (sh_cx + 10, controls_cy + 3), (sh_cx + 10, controls_cy + 13)], fill=(255, 255, 255, 140))
            draw.polygon([(sh_cx + 18, controls_cy - 8), (sh_cx + 10, controls_cy - 13), (sh_cx + 10, controls_cy - 3)], fill=(255, 255, 255, 140))
            
            # Previous (◀◀) - Two solid triangles pointing left
            draw.polygon([(pr_cx - 9, controls_cy), (pr_cx + 6, controls_cy - 12), (pr_cx + 6, controls_cy + 12)], fill=(255, 255, 255, 255))
            draw.polygon([(pr_cx - 24, controls_cy), (pr_cx - 9, controls_cy - 12), (pr_cx - 9, controls_cy + 12)], fill=(255, 255, 255, 255))
            
            # Pause (||) - Two thick elegant vertical lines
            draw.rectangle((pa_cx - 8, controls_cy - 15, pa_cx - 2, controls_cy + 15), fill=(255, 255, 255, 255))
            draw.rectangle((pa_cx + 2, controls_cy - 15, pa_cx + 8, controls_cy + 15), fill=(255, 255, 255, 255))
            
            # Next (▶▶) - Two solid triangles pointing right
            draw.polygon([(ne_cx + 9, controls_cy), (ne_cx - 6, controls_cy - 12), (ne_cx - 6, controls_cy + 12)], fill=(255, 255, 255, 255))
            draw.polygon([(ne_cx + 24, controls_cy), (ne_cx + 9, controls_cy - 12), (ne_cx + 9, controls_cy + 12)], fill=(255, 255, 255, 255))
            
            # Repeat Loop (rounded rectangle with arrowheads pointing left and right)
            draw.arc((rp_cx - 18, controls_cy - 10, rp_cx - 6, controls_cy + 10), start=90, end=270, fill=(255, 255, 255, 140), width=3)
            draw.arc((rp_cx + 6, controls_cy - 10, rp_cx + 18, controls_cy + 10), start=270, end=90, fill=(255, 255, 255, 140), width=3)
            draw.line([(rp_cx - 12, controls_cy - 10), (rp_cx + 12, controls_cy - 10)], fill=(255, 255, 255, 140), width=3)
            draw.line([(rp_cx - 12, controls_cy + 10), (rp_cx + 12, controls_cy + 10)], fill=(255, 255, 255, 140), width=3)
            draw.polygon([(rp_cx + 9, controls_cy - 10), (rp_cx + 3, controls_cy - 15), (rp_cx + 3, controls_cy - 5)], fill=(255, 255, 255, 140))
            draw.polygon([(rp_cx - 9, controls_cy + 10), (rp_cx - 3, controls_cy + 5), (rp_cx - 3, controls_cy + 15)], fill=(255, 255, 255, 140))

            out = bg.convert("RGB")
            # Resize the final image to 1280x720 to match Style 1 dimensions
            out = out.resize((1280, 720), Image.Resampling.LANCZOS)
            os.makedirs("cache", exist_ok=True)
            out.save(final_path, "PNG")
            
            try:
                os.remove(raw_path)
            except Exception:
                pass
                
            return final_path

        # ----------------- STYLE 1: Classic Glassmorphic Card (Fallback/Original) -----------------
        # Dimensions for thumbnail
        bg_ratio = W / H
        src_ratio = src.width / src.height
        if src_ratio > bg_ratio:
            new_w = int(src.height * bg_ratio)
            offset = (src.width - new_w) // 2
            bg = src.crop((offset, 0, offset + new_w, src.height))
        else:
            new_h = int(src.width / bg_ratio)
            offset = (src.height - new_h) // 2
            bg = src.crop((0, offset, src.width, offset + new_h))
            
        bg = bg.resize((W, H), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(60))
        
        # Darken background slightly
        bg_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 100))
        bg = Image.alpha_composite(bg, bg_overlay)
        
        # 2. Card Dimensions
        card_w = 460
        card_h = 620
        card_x = (W - card_w) // 2
        card_y = (H - card_h) // 2
        card_radius = 20
        
        # Shadow for Card
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_shadow = ImageDraw.Draw(shadow)
        draw_shadow.rounded_rectangle(
            (card_x - 10, card_y - 10, card_x + card_w + 10, card_y + card_h + 10),
            radius=card_radius + 10,
            fill=(0, 0, 0, 150)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(20))
        bg = Image.alpha_composite(bg, shadow)
        
        # Card itself
        card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_card = ImageDraw.Draw(card)
        draw_card.rounded_rectangle(
            (card_x, card_y, card_x + card_w, card_y + card_h),
            radius=card_radius,
            fill=(255, 255, 255, 255)
        )
        bg = Image.alpha_composite(bg, card)
        
        # 3. Paste Cover Art on Card
        padding = 24
        cover_w = card_w - (padding * 2)
        cover_h = cover_w
        
        cover_x = card_x + padding
        cover_y = card_y + padding
        cover_radius = 12
        
        cover_resized = src.resize((cover_w, cover_h), Image.Resampling.LANCZOS)
        cover_mask = Image.new("L", (cover_w, cover_h), 0)
        ImageDraw.Draw(cover_mask).rounded_rectangle((0, 0, cover_w, cover_h), radius=cover_radius, fill=255)
        
        bg.paste(cover_resized, (cover_x, cover_y), cover_mask)
        
        # 4. Add Text
        draw = ImageDraw.Draw(bg)
        
        title_font = safe_font("Opus/assets/font.ttf", 35)
        artist_font = safe_font("Opus/assets/font2.ttf", 25)
        logo_font = safe_font("Opus/assets/font.ttf", 20)
        
        center_x = card_x + (card_w // 2)
        title_y = cover_y + cover_h + 20
        
        title_draw = ellipsize(title, title_font, cover_w)
        artist_draw = ellipsize(channel, artist_font, cover_w)
        
        if align == "center":
            center_x = card_x + (card_w // 2)
            title_w = draw.textbbox((0, 0), title_draw, font=title_font)[2]
            draw.text((center_x - (title_w // 2), title_y), title_draw, fill=(0, 0, 0, 255), font=title_font)
            
            artist_y = title_y + 40
            artist_w = draw.textbbox((0, 0), artist_draw, font=artist_font)[2]
            draw.text((center_x - (artist_w // 2), artist_y), artist_draw, fill=(100, 100, 100, 255), font=artist_font)
            
            logo_text = "Stormify 26.5"
            logo_y = card_y + card_h - padding - 20
            logo_w = draw.textbbox((0, 0), logo_text, font=logo_font)[2]
            draw.text((center_x - (logo_w // 2), logo_y), logo_text, fill=(150, 150, 150, 255), font=logo_font)
        else:
            text_x = cover_x
            draw.text((text_x, title_y), title_draw, fill=(0, 0, 0, 255), font=title_font)
            
            artist_y = title_y + 40
            draw.text((text_x, artist_y), artist_draw, fill=(100, 100, 100, 255), font=artist_font)
            
            logo_text = "Stormify 26.5"
            logo_y = card_y + card_h - padding - 20
            draw.text((text_x, logo_y), logo_text, fill=(150, 150, 150, 255), font=logo_font)
        
        out = bg.convert("RGB")
        os.makedirs("cache", exist_ok=True)
        out.save(final_path, "PNG")

        try:
            os.remove(raw_path)
        except Exception:
            pass

        return final_path

    except Exception as e:
        print(f"[get_thumb error] {e}")
        return FAILED

async def gen_qthumb(text, userid, videoid=None, thumbnail_url=None):
    final_path = f"cache/queue_{userid}.png"
    # Dimensions
    W, H = 1280, 720
    
    # 1. Background
    bg = None
    if thumbnail_url or videoid:
        try:
            os.makedirs("cache", exist_ok=True)
            raw_path = f"cache/raw_q_{userid}.jpg"
            
            if not thumbnail_url and videoid:
                # Try to get thumbnail URL if only videoid is provided (rare but possible)
                search = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
                try:
                    results = await search.next()
                except TypeError:
                    results = search.result()
                if results and "result" in results and results["result"]:
                    r0 = results["result"][0]
                    thumb_field = r0.get("thumbnails") or r0.get("thumbnail") or []
                    if isinstance(thumb_field, list) and thumb_field:
                        thumbnail_url = (thumb_field[0].get("url") or "").split("?")[0]
                    elif isinstance(thumb_field, dict):
                        thumbnail_url = (thumb_field.get("url") or "").split("?")[0]

            if thumbnail_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(thumbnail_url) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(raw_path, "wb") as f:
                                await f.write(await resp.read())
                            
                            src = Image.open(raw_path).convert("RGBA")
                            
                            # Same crop/resize/blur logic as get_thumb
                            bg_ratio = W / H
                            src_ratio = src.width / src.height
                            if src_ratio > bg_ratio:
                                new_w = int(src.height * bg_ratio)
                                offset = (src.width - new_w) // 2
                                bg = src.crop((offset, 0, offset + new_w, src.height))
                            else:
                                new_h = int(src.width / bg_ratio)
                                offset = (src.height - new_h) // 2
                                bg = src.crop((0, offset, src.width, offset + new_h))
                                
                            bg = bg.resize((W, H), Image.Resampling.LANCZOS)
                            bg = bg.filter(ImageFilter.GaussianBlur(60))
                            
                            # Darken background slightly
                            bg_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 120))
                            bg = Image.alpha_composite(bg, bg_overlay)
                            
                            try: os.remove(raw_path)
                            except: pass
        except Exception as e:
            print(f"[gen_qthumb bg error] {e}")

    if bg is None:
        # Fallback to soft gradient/blur background if thumbnail fails
        bg = Image.new("RGBA", (W, H), (20, 20, 20, 255))
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        d.ellipse([W//2, -100, W+200, H//2], fill=(255, 45, 85, 80))
        d.ellipse([-200, H//2, W//2, H+200], fill=(0, 122, 255, 60))
        overlay = overlay.filter(ImageFilter.GaussianBlur(100))
        bg = Image.alpha_composite(bg, overlay)
    
    # 2. Card
    card_w = 900
    card_h = 550
    card_x = (W - card_w) // 2
    card_y = (H - card_h) // 2
    card_radius = 30
    
    # Shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_shadow = ImageDraw.Draw(shadow)
    draw_shadow.rounded_rectangle(
        (card_x - 15, card_y - 15, card_x + card_w + 15, card_y + card_h + 15),
        radius=card_radius + 15,
        fill=(0, 0, 0, 100)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    bg = Image.alpha_composite(bg, shadow)
    
    # White Glassmorphism Card
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_card = ImageDraw.Draw(card)
    draw_card.rounded_rectangle(
        (card_x, card_y, card_x + card_w, card_y + card_h),
        radius=card_radius,
        fill=(255, 255, 255, 240)
    )
    bg = Image.alpha_composite(bg, card)
    
    # 3. Text
    draw = ImageDraw.Draw(bg)
    header_font = safe_font("Opus/assets/font.ttf", 40)
    text_font = safe_font("Opus/assets/font2.ttf", 24)
    logo_font = safe_font("Opus/assets/font.ttf", 22)
    
    # Header
    draw.text((card_x + 50, card_y + 40), "QUEUED PLAYLIST", fill=(0, 0, 0, 255), font=header_font)
    
    # Separator line
    draw.line((card_x + 50, card_y + 100, card_x + card_w - 50, card_y + 100), fill=(200, 200, 200, 255), width=2)
    
    # Playlist Items
    y_offset = card_y + 130
    lines = text.split("\n")
    for line in lines[:10]: # Limit to 10 for safety
        if not line.strip(): continue
        # Transliterate line for thumbnail rendering
        clean_line = unidecode(unicodedata.normalize('NFKD', line.strip()))
        # Handle "Queued Position-" lines by graying them out
        if "Queued Position-" in clean_line:
            draw.text((card_x + 70, y_offset), clean_line, fill=(140, 140, 140, 255), font=text_font)
            y_offset += 35
        else:
            draw.text((card_x + 50, y_offset), clean_line, fill=(40, 40, 40, 255), font=text_font)
            y_offset += 40
            
    # Logo
    logo_text = "Stormify 26.5"
    draw.text((card_x + 50, card_y + card_h - 50), logo_text, fill=(160, 160, 160, 255), font=logo_font)
    
    os.makedirs("cache", exist_ok=True)
    bg.convert("RGB").save(final_path)
    return final_path

async def gen_bixy_wrapped(user_id, user_name, total_played, top_songs):
    final_path = f"cache/wrapped_{user_id}.png"
    
    W, H = 1080, 1920
    
    # Premium gradient background (Deep purple/black for Bixy)
    bg = Image.new("RGBA", (W, H), (15, 10, 25, 255))
    draw = ImageDraw.Draw(bg)
    
    # Draw some ambient glows
    glow1 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_glow1 = ImageDraw.Draw(glow1)
    d_glow1.ellipse([-400, -400, 800, 800], fill=(138, 43, 226, 40)) # Purple glow top left
    d_glow1.ellipse([W-600, H-600, W+400, H+400], fill=(75, 0, 130, 50)) # Indigo bottom right
    glow1 = glow1.filter(ImageFilter.GaussianBlur(200))
    bg = Image.alpha_composite(bg, glow1)

    # Fonts
    title_font = safe_font("Opus/assets/font.ttf", 100)
    sub_font = safe_font("Opus/assets/font.ttf", 60)
    text_font = safe_font("Opus/assets/font2.ttf", 45)
    number_font = safe_font("Opus/assets/font.ttf", 55)
    
    # 1. Header
    draw.text((80, 150), f"BIXY", fill=(255, 255, 255, 255), font=title_font)
    draw.text((80, 260), f"WRAPPED 2026", fill=(180, 150, 255, 255), font=sub_font)
    
    # 2. User info
    draw.text((80, 420), f"{unidecode(unicodedata.normalize('NFKD', user_name))}'s Music Journey", fill=(220, 220, 220, 255), font=sub_font)
    
    # 3. Total Played box
    card_y = 550
    draw.rounded_rectangle((80, card_y, W-80, card_y + 200), radius=30, fill=(255, 255, 255, 15))
    draw.text((120, card_y + 40), "Total Songs Played", fill=(200, 200, 200, 255), font=text_font)
    draw.text((120, card_y + 100), f"{total_played}", fill=(255, 255, 255, 255), font=title_font)
    
    # 4. Top Songs
    top_y = 820
    draw.text((80, top_y), "Your Top Tracks", fill=(255, 255, 255, 255), font=sub_font)
    
    y_offset = top_y + 100
    for i, (vidid, data) in enumerate(top_songs[:5]):
        title = unidecode(unicodedata.normalize('NFKD', data["title"]))[:32]
        count = data["count"]
        
        # Song card
        draw.rounded_rectangle((80, y_offset, W-80, y_offset + 140), radius=20, fill=(255, 255, 255, 8))
        
        # Rank number
        draw.text((120, y_offset + 40), f"#{i+1}", fill=(180, 150, 255, 255), font=number_font)
        
        # Title
        draw.text((230, y_offset + 25), title + ("..." if len(data["title"]) > 32 else ""), fill=(255, 255, 255, 255), font=text_font)
        # Plays
        draw.text((230, y_offset + 80), f"{count} Plays", fill=(150, 150, 150, 255), font=safe_font("Opus/assets/font2.ttf", 35))
        
        y_offset += 170

    # Footer
    draw.text((W//2 - 200, H - 150), "Listen on Bixy Music", fill=(100, 100, 100, 255), font=text_font)

    os.makedirs("cache", exist_ok=True)
    bg.convert("RGB").save(final_path)
    return final_path
