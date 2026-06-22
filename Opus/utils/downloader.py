import asyncio
import os
import re
from typing import Optional, Dict, Union, List

import aiofiles
import httpx
from yt_dlp import YoutubeDL
from config import API_URL

cookies_file = "Opus/assets/cookies.txt"
download_folder = "downloads"
os.makedirs(download_folder, exist_ok=True)

class DummyLogger:
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        pass


API_DOWNLOAD_MAX_RETRIES = 1
CHUNK_SIZE = 12 * 1024 * 1024
API_TIMEOUT_SECONDS = 20
concurrent_fragment_downloads = 60

# Global tracking for active download progress (user_id -> percentage)
DOWNLOAD_PROGRESS = {}


def extract_video_id(link: str) -> str:
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    m = re.search(r"youtu\.be/([A-Za-z0-9_\-]{6,})", link)
    if m:
        return m.group(1)
    m = re.search(r"youtube\.com/shorts/([A-Za-z0-9_\-]{6,})", link)
    if m:
        return m.group(1)
    m = re.search(r"youtube\.com/embed/([A-Za-z0-9_\-]{6,})", link)
    if m:
        return m.group(1)
    return link.split("/")[-1].split("?")[0]

def safe_filename(name: str) -> str:
    # Preserve spaces but remove illegal characters
    return re.sub(r'[\\/*?:"<>|]', "", (name or "").strip())[:150]

def file_exists(video_id: str, file_type: str = "audio") -> Optional[str]:
    exts = ["mp3", "m4a", "opus", "webm", "mp4", "mkv"] if file_type == "audio" else ["mp4", "mkv", "webm"]
    for ext in exts:
        path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    for file in os.listdir(download_folder):
        for ext in exts:
            if file.endswith(f".{ext}") and file.startswith(video_id):
                full = f"{download_folder}/{file}"
                if os.path.getsize(full) > 0:
                    return full
    return None


def _ext_from_filename(fn: str, default: str) -> str:
    if "." in fn:
        ext = fn.rsplit(".", 1)[-1].lower()
        if re.fullmatch(r"[0-9a-z]{1,6}", ext):
            return ext
    return default


async def api_download(link: str, file_type: str = "audio", audio_format: str = "m4a", user_id: Optional[int] = None) -> Optional[str]:
    if "youtube.com" not in link and "youtu.be" not in link:
        video_id = extract_video_id(link)
        link = f"https://www.youtube.com/watch?v={video_id}"
    else:
        video_id = extract_video_id(link)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    }
    timeout = httpx.Timeout(API_TIMEOUT_SECONDS)
    
    # 1. Use the powerful YouTube concurrent resolver
    try:
        from Opus.platforms.Youtube import YouTubeAPI
        yt_api = YouTubeAPI()
        success, stream_url = await yt_api.video(link, is_video=(file_type == "video"))
        if success == 2 and stream_url:
            if os.path.exists(stream_url) and os.path.getsize(stream_url) > 10240:
                return stream_url
        if success and stream_url:
            download_url = stream_url
        else:
            download_url = None
    except Exception as e:
        print(f"[api_download] Error using YouTube API resolver: {e}")
        download_url = None

    # 2. Fallback to older API_URL logic
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            if not download_url:
                if file_type == "audio":
                    url = f"{API_URL}/mp3?id={video_id}"
                else:
                    q = str(audio_format or "360").replace("p", "")
                    url = f"{API_URL}/download?id={video_id}&format={q}"
                resp = await client.get(url)
                if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                    data = resp.json() if resp.content else {}
                    download_url = data.get("downloadUrl")

            if not download_url:
                return None
            ext = _ext_from_filename(download_url.split("/")[-1], "mp3" if file_type == "audio" else "mp4")
            path = f"{download_folder}/{video_id}.{ext}"
            for _ in range(API_DOWNLOAD_MAX_RETRIES):
                try:
                    async with client.stream("GET", download_url) as r:
                        if r.status_code != 200:
                            continue
                        total_size = int(r.headers.get("content-length", 0))
                        bytes_downloaded = 0
                        async with aiofiles.open(path, "wb") as f:
                            async for chunk in r.aiter_bytes(CHUNK_SIZE):
                                if chunk:
                                    await f.write(chunk)
                                    bytes_downloaded += len(chunk)
                                    if total_size > 0 and user_id is not None:
                                        percent = min(99, int((bytes_downloaded / total_size) * 100))
                                        DOWNLOAD_PROGRESS[user_id] = percent
                except Exception:
                    continue
                if os.path.exists(path) and os.path.getsize(path) > 1024 * 100:
                    return path
            return None
    except Exception as e:
        print(f"[api_download] Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def _download_ytdlp(link: str, opts: Dict) -> Union[None, str, List[str]]:
    try:
        print(f"[_download_ytdlp] Extracting info for link: {link}")
        with YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(link, download=False)
            except Exception as e:
                print(f"[_download_ytdlp] Initial extract_info failed: {e}. Retrying format best...")
                opts["format"] = "best"
                with YoutubeDL(opts) as ydl2:
                    info = ydl2.extract_info(link, download=False)
            if "entries" in info:
                print(f"[_download_ytdlp] Playlist detected. Downloading entries...")
                ydl.download([link])
                results = []
                for entry in info["entries"]:
                    vid = entry.get("id")
                    if not vid:
                        continue
                    for f in os.listdir(download_folder):
                        if f.startswith(vid):
                            p = f"{download_folder}/{f}"
                            if os.path.getsize(p) > 0:
                                results.append(p)
                return results
            vid = info.get("id")
            print(f"[_download_ytdlp] Single video ID {vid} found. Starting download...")
            ydl.download([link])
            for f in os.listdir(download_folder):
                if f.startswith(vid):
                    p = f"{download_folder}/{f}"
                    if os.path.getsize(p) > 0:
                        print(f"[_download_ytdlp] Download completed successfully: {p}")
                        return p
            print(f"[_download_ytdlp] Download completed but no matching file found in {download_folder} starting with {vid}")
            return None
    except Exception as e:
        print(f"[_download_ytdlp] Exception in _download_ytdlp: {e}")
        import traceback
        traceback.print_exc()
        return None

async def yt_dlp_download(link: str, type: str, format_id: str = None, outtmpl: Optional[str] = None, user_id: Optional[int] = None):
    loop = asyncio.get_running_loop()
    opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": DummyLogger(),
        "geo_bypass": True,
        "concurrent_fragment_downloads": concurrent_fragment_downloads,
        "outtmpl": outtmpl or f"{download_folder}/%(id)s.%(ext)s",
        "js_runtimes": {"node": {}, "deno": {}},
        "remote_components": ["ejs:github"],
    }
    
    if user_id is not None:
        def progress_hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    percent = min(99, int((downloaded / total) * 100))
                    DOWNLOAD_PROGRESS[user_id] = percent
        opts["progress_hooks"] = [progress_hook]

    try:
        import config
        config.check_and_refresh_cookies(force=False)
    except Exception:
        pass

    if os.path.exists(cookies_file) and os.path.getsize(cookies_file) > 0:
        opts["cookiefile"] = cookies_file

    if type in ["audio", "song_audio"]:
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }, {
                "key": "EmbedThumbnail",
            }, {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            }],
        })
    else:
        opts.update({
            "format": format_id or "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "merge_output_format": "mp4",
            "prefer_ffmpeg": True,
        })

    res = await loop.run_in_executor(None, _download_ytdlp, link, opts)
    if not res and "cookiefile" in opts:
        opts.pop("cookiefile", None)
        res = await loop.run_in_executor(None, _download_ytdlp, link, opts)
    return res




async def apply_metadata(file_path: str, title: str, performer: str, thumb_path: Optional[str] = None):
    """Embed Title, Artist (performer), and Thumbnail into an audio file using FFmpeg"""
    if not os.path.exists(file_path):
        return
    
    # We create a temporary file for the metadata-applied version
    ext = file_path.split(".")[-1]
    temp_output = f"{file_path}_meta.{ext}"
    
    # Base command for metadata
    cmd = [
        "ffmpeg", "-y", "-i", file_path,
    ]
    
    # Add thumbnail if exists
    if thumb_path and os.path.exists(thumb_path):
        cmd.extend(["-i", thumb_path])
        # Map audio from 1st input and image from 2nd input
        cmd.extend(["-map", "0:0", "-map", "1:0", "-c", "copy", "-id3v2_version", "3"])
        # Set album art disposition for MP3
        cmd.extend(["-disposition:v", "attached_pic"])
    else:
        cmd.extend(["-c", "copy"])
    
    # Add metadata tags
    cmd.extend([
        "-metadata", f"title={title}",
        "-metadata", f"artist={performer}",
        "-metadata", f"album_artist=Aurex Music",
        "-metadata", f"comment=Crafted to be heard. Built to be felt.",
        temp_output
    ])
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        
        if os.path.exists(temp_output) and os.path.getsize(temp_output) > 1024:
            # Replace original with metadata-applied version
            os.replace(temp_output, file_path)
            return True
    except Exception as e:
        print(f"[Metadata] Error applying metadata: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
    return False



async def download_audio(link: str, title: Optional[str] = None, duration_sec: int = 0, user_id: Optional[int] = None) -> Optional[str]:
    vid = extract_video_id(link)
    existing = file_exists(vid, "audio")
    if existing:
        if user_id is not None:
            DOWNLOAD_PROGRESS[user_id] = 100
        return existing
    
    # Try direct download if it looks like a direct URL
    if link.startswith("http") and not any(x in link for x in ["youtube.com", "youtu.be"]):
        direct = await download_url(link, user_id=user_id)
        if direct:
            return direct

    api = await api_download(link, "audio", "mp3", user_id=user_id)
    if api:
        return api
    
    # yt-dlp full download is completely disabled for streaming to avoid cloud IP bans
    # res = await yt_dlp_download(link, "audio", user_id=user_id)
    # if res:
    #     return res[0] if isinstance(res, list) else res
    
    return None


async def download_url(url: str, user_id: Optional[int] = None) -> Optional[str]:
    video_id = extract_video_id(url)
    ext = _ext_from_filename(url.split("/")[-1], "mp3")
    path = f"{download_folder}/{video_id}.{ext}"
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    }
    timeout = httpx.Timeout(API_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            async with client.stream("GET", url) as r:
                if r.status_code != 200:
                    return None
                total_size = int(r.headers.get("content-length", 0))
                bytes_downloaded = 0
                async with aiofiles.open(path, "wb") as f:
                    async for chunk in r.aiter_bytes(CHUNK_SIZE):
                        if chunk:
                            await f.write(chunk)
                            bytes_downloaded += len(chunk)
                            if total_size > 0 and user_id is not None:
                                percent = min(99, int((bytes_downloaded / total_size) * 100))
                                DOWNLOAD_PROGRESS[user_id] = percent
        if os.path.exists(path) and os.path.getsize(path) > 1024 * 10:
            return path
    except Exception as e:
        print(f"Direct download error: {e}")
    return None


async def download_video(link: str, quality: int = 360) -> Optional[str]:
    vid = extract_video_id(link)
    existing = file_exists(vid, "video")
    if existing:
        return existing
    api = await api_download(link, "video", str(quality))
    if api:
        return api
    # yt-dlp full download is completely disabled for streaming to avoid cloud IP bans
    # res = await yt_dlp_download(link, "video")
    # return res[0] if isinstance(res, list) else res
    return None


async def download_song_audio(link: str, format_id: Optional[str], title: str) -> Optional[str]:
    # Prioritize api_download to avoid VPS cloud IP bans and speed up song downloads!
    api = await api_download(link, "audio", "mp3")
    if api:
        safe = safe_filename(title or "audio")
        dest = f"{download_folder}/{safe}.mp3"
        try:
            os.rename(api, dest)
            return dest
        except Exception:
            return api
            
    safe = safe_filename(title or "audio")
    outtmpl = f"{download_folder}/{safe}.%(ext)s"
    res = await yt_dlp_download(link, "song_audio", format_id, outtmpl)
    return res[0] if isinstance(res, list) else res


async def download_song_video(link: str, format_id: Optional[str], title: str) -> Optional[str]:
    # Prioritize api_download to avoid VPS cloud IP bans and speed up song downloads!
    api = await api_download(link, "video", "360")
    if api:
        safe = safe_filename(title or "video")
        dest = f"{download_folder}/{safe}.mp4"
        try:
            os.rename(api, dest)
            return dest
        except Exception:
            return api

    safe = safe_filename(title or "video")
    outtmpl = f"{download_folder}/{safe}.%(ext)s"
    res = await yt_dlp_download(link, "video", format_id, outtmpl)
    return res[0] if isinstance(res, list) else res
