import os
import re
import json

import httpx
import yt_dlp
import asyncio
import aiofiles
import config

from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from typing import Dict, List, Optional, Tuple, Union
from youtubesearchpython.future import VideosSearch, Recommendations
from urllib.parse import urlparse

from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds, seconds_to_min
from Opus.utils.downloader import (
    download_audio,
    download_video,
    download_song_audio,
    download_song_video,
    extract_video_id,
)

COOKIE_PATH = "Opus/assets/cookies.txt"
DOWNLOAD_DIR = "downloads"
CHUNK_SIZE = 8 * 1024 * 1024

class DummyLogger:
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        pass

_DETAILS_CACHE = {}
_STREAM_CACHE = {}




def _cookiefile_path() -> Optional[str]:
    try:
        config.check_and_refresh_cookies(force=False)
    except Exception:
        pass
    path = str(COOKIE_PATH)
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception:
        pass
    return None


def _cookies_args() -> List[str]:
    p = _cookiefile_path()
    return ["--cookies", p] if p else []


import sys

async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    cmd_args = list(args)
    if cmd_args[0] == "yt-dlp":
        cmd_args = [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node,deno", "--remote-components", "ejs:github"] + cmd_args[1:]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=25)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return b"", b""
    return stdout, stderr


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]+', "_", (name or "").strip())[:200]


async def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30, connect=10.0, read=30.0),
        limits=httpx.Limits(max_keepalive_connections=None, max_connections=None, keepalive_expiry=300.0),
        follow_redirects=True,
    )


def _clean_title(title: str) -> str:
    # Remove common YouTube suffixes and prefixes
    title = re.sub(r"\(Official.*?\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\[Official.*?\]", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\(Video.*?\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\[Video.*?\]", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\(Audio.*?\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\[Audio.*?\]", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\(Lyrics.*?\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\[Lyrics.*?\]", "", title, flags=re.IGNORECASE)
    return title.strip()


class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()
        elif videoid is True and link and not any(x in link for x in ("youtube.com", "youtu.be", "://", " ")):
            link = self.base_url + link
        elif link and not any(x in link for x in ("youtube.com", "youtu.be", "://", " ")):
            link = self.base_url + link
            
        link = (link or "").strip()
        if len(link) > 2048:
            raise ValueError("Invalid link")
        if self._url_pattern.search(link):
            parsed = urlparse(link)
            host = (parsed.hostname or "").lower()
            if not (host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")):
                raise ValueError("Unsupported host")
        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "/live/" in link:
            link = self.base_url + link.split("/live/")[-1].split("?")[0]
        elif "/shorts/" in link:
            link = self.base_url + link.split("/shorts/")[-1].split("?")[0]
        return link.split("&")[0]

    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        try:
            prepared = self._prepare_link(link, videoid)
        except ValueError:
            return False
        return bool(self._url_pattern.search(prepared))

    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url
        return None

    async def _fetch_video_info(self, query: str) -> Optional[Dict]:
        try:
            prepared = self._prepare_link(query)
        except ValueError:
            prepared = (query or "").strip()
            
        is_link = bool(self._url_pattern.search(prepared))
        
        if is_link:
            try:
                data = await VideosSearch(prepared, limit=1).next()
                result = data.get("result", [])
                if result:
                    info = result[0]
                    info["webpage_url"] = self.base_url + info.get("id", "")
                    if "thumbnails" not in info or not info.get("thumbnails"):
                        info["thumbnails"] = [{"url": info.get("thumbnail", "")}]
                    return info
            except Exception:
                pass
                
            stdout, _ = await _exec_proc("yt-dlp", "--quiet", "--no-warnings", *(_cookies_args()), "--dump-json", prepared)
            if not stdout:
                stdout, _ = await _exec_proc("yt-dlp", "--quiet", "--no-warnings", "--dump-json", prepared)
            if not stdout:
                return None
            try:
                info = json.loads(stdout.decode())
                if isinstance(info.get("duration"), int):
                    info["duration"] = seconds_to_min(info["duration"]) if info.get("duration") else None
                if "thumbnails" not in info:
                    info["thumbnails"] = [{"url": info.get("thumbnail", "")}]
                info["webpage_url"] = info.get("webpage_url", prepared)
                return info
            except json.JSONDecodeError:
                return None
        else:
            try:
                data = await VideosSearch(prepared, limit=7).next()
                result = data.get("result", [])
                if not result:
                    return None
                    
                best_info = result[0]
                best_score = -100
                
                query_lower = prepared.lower()
                wants_live = "live" in query_lower
                wants_cover = "cover" in query_lower
                wants_karaoke = "karaoke" in query_lower
                wants_inst = "instrumental" in query_lower or "inst" in query_lower
                wants_remix = "remix" in query_lower
                wants_slowed = "slowed" in query_lower or "reverb" in query_lower
                wants_lofi = "lofi" in query_lower or "lo-fi" in query_lower
                wants_8d = "8d" in query_lower
                
                for info in result:
                    score = 0
                    title = info.get("title", "").lower()
                    
                    if not wants_live and "live" in title:
                        score -= 15
                    if not wants_cover and "cover" in title:
                        score -= 15
                    if not wants_karaoke and ("karaoke" in title):
                        score -= 15
                    if not wants_inst and ("instrumental" in title or "inst." in title):
                        score -= 15
                    if not wants_remix and "remix" in title:
                        score -= 5
                    if not wants_slowed and ("slowed" in title or "reverb" in title):
                        score -= 20
                    if not wants_lofi and ("lofi" in title or "lo-fi" in title):
                        score -= 20
                    if not wants_8d and "8d" in title:
                        score -= 20
                        
                    if "1 hour" in title or "loop" in title or "10 hours" in title or "compilation" in title:
                        score -= 10
                    
                    if "audio" in title or "lyric" in title or "lyrics" in title:
                        score += 3
                        
                    channel_name = info.get("channel", {}).get("name", "").lower()
                    if "vevo" in channel_name or "official" in channel_name or "topic" in channel_name or "music" in channel_name:
                        score += 2
                        
                    dur_str = info.get("duration")
                    if dur_str:
                        parts = dur_str.split(":")
                        if len(parts) == 2:
                            mins = int(parts[0])
                            if 2 <= mins <= 6:
                                score += 2
                            elif mins > 10:
                                score -= 5
                        elif len(parts) > 2:
                            score -= 15
                    else:
                        if not wants_live:
                            score -= 5
                            
                    if score > best_score:
                        best_score = score
                        best_info = info
                
                info = best_info
                info["webpage_url"] = self.base_url + info.get("id", "")
                if "thumbnails" not in info or not info.get("thumbnails"):
                    info["thumbnails"] = [{"url": info.get("thumbnail", "")}]
                return info
            except Exception:
                return None

    async def is_live(self, link: str) -> bool:
        prepared = self._prepare_link(link)
        stdout, _ = await _exec_proc("yt-dlp", "--quiet", "--no-warnings", *(_cookies_args()), "--dump-json", prepared)
        if not stdout:
            stdout, _ = await _exec_proc("yt-dlp", "--quiet", "--no-warnings", "--dump-json", prepared)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode())
            return bool(info.get("is_live"))
        except json.JSONDecodeError:
            return False

    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str, str]:
        cache_key = videoid if isinstance(videoid, str) and videoid.strip() else extract_video_id(link)
        if cache_key in _DETAILS_CACHE:
            return _DETAILS_CACHE[cache_key]
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Video not found")
        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        performer = info.get("channel", "YouTube")
        if isinstance(performer, dict):
            performer = performer.get("name", "YouTube")
        res = (info.get("title", ""), dt, ds, thumb, info.get("id", ""), str(performer))
        _DETAILS_CACHE[cache_key] = res
        return res

    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0] if info else ""

    async def _probe_url(self, url: str, timeout: int = 4) -> bool:
        """Light check if a URL is reachable and serves media (not an error page)."""
        try:
            # googlevideo URLs are always valid if we got them from an API
            if "googlevideo.com" in url:
                return True
            async with await _http_client() as client:
                resp = await client.head(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    follow_redirects=True,
                    timeout=timeout,
                )
                # Accept any success status
                if resp.status_code in (200, 206):
                    ct = resp.headers.get("content-type", "").lower()
                    # Reject HTML error pages
                    if "html" in ct:
                        return False
                    return True
                return False
        except Exception:
            return False

    async def video(self, link: str, videoid: Union[str, bool, None] = None, is_video: bool = False, title: str = None) -> Tuple[int, str]:
        """Resolve a YouTube video to a streamable URL or downloaded file.
        
        Returns:
            (1, url)        - Direct streamable URL (googlevideo, CDN, worker)
            (2, local_path) - Downloaded file for local/dash streaming
            (0, "")         - All methods failed
        
        API Priority:
            1. utube-ecru   → googlevideo URLs (best for direct streaming)
            2. honox        → CDN download URLs (download-friendly)
            3. cobalt       → tunnel/CDN URLs (download-friendly)
            4. bxyt worker  → direct stream proxy
            5. honox search → search by title, resolve via utube-ecru
        """
        import time
        from Opus.utils.api_logs import log_api
        def print(*args, **kwargs):
            msg = " ".join(str(arg) for arg in args)
            log_api(msg)

        link = self._prepare_link(link, videoid)
        video_id = videoid if isinstance(videoid, str) else extract_video_id(link)
        
        # 1. Check in-memory cache (5 minutes expiration)
        now = time.time()
        if video_id in _STREAM_CACHE:
            ts, cached_url = _STREAM_CACHE[video_id]
            if now - ts < 300:
                if await self._probe_url(cached_url, timeout=4):
                    return 1, cached_url
        
        # 2. Run API resolvers concurrently
        # Each resolver returns (url, is_streamable) or None
        # is_streamable=True means URL can be streamed directly (googlevideo, worker proxy)
        # is_streamable=False means URL should be downloaded first (CDN, tunnel)

        async def try_cobalt():
            """Cobalt API via ashlynn — GET with query params."""
            cobalt_base = config.COBALT_API_URL
            if not cobalt_base:
                return None
            # Also try user-configured cobalt if set
            cobalt_urls = [cobalt_base]
            if config.API_URL1 and config.API_URL1 != cobalt_base:
                cobalt_urls.insert(0, config.API_URL1)
            
            for cobalt_url in cobalt_urls:
                try:
                    mode = "video" if is_video else "audio"
                    api_url = f"{cobalt_url}?url={link}&downloadMode={mode}"
                    async with await _http_client() as client:
                        resp = await client.get(
                            api_url,
                            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            direct_url = data.get("url") or data.get("data", {}).get("url")
                            if direct_url:
                                print(f"[YouTube.video] Cobalt resolved via {cobalt_url}: {direct_url[:80]}...")
                                # Cobalt tunnel URLs are download-only, not directly streamable
                                return (direct_url, False)
                except Exception as e:
                    print(f"[YouTube.video] Cobalt API {cobalt_url} failed: {e}")
            return None

        async def try_honox():
            """Honox/Space YT DL API — /download?id=...&format=..."""
            honox_base = config.HONOX_API_URL.rstrip('/') if config.HONOX_API_URL else None
            if not honox_base:
                return None
            try:
                fmt = "720" if is_video else "mp3"
                api_url = f"{honox_base}/download?id={video_id}&format={fmt}"
                async with await _http_client() as client:
                    resp = await client.get(api_url, timeout=8)
                    if resp.status_code == 200:
                        data = resp.json()
                        direct_url = (
                            data.get("download_url")
                            or data.get("downloadUrl")
                            or data.get("url")
                            or data.get("link")
                        )
                        if direct_url:
                            print(f"[YouTube.video] Honox resolved: {direct_url[:80]}...")
                            # If it's a googlevideo URL, it's directly streamable
                            streamable = "googlevideo.com" in direct_url
                            return (direct_url, streamable)
            except Exception as e:
                print(f"[YouTube.video] Honox API failed: {e}")
            return None

        async def try_utube_ecru():
            """Synczen worker — returns googlevideo streaming URLs and tests streamability."""
            try:
                api_url = f"https://sweet-scene-7486.synczen.workers.dev/?q={video_id}"
                async with await _http_client() as client:
                    resp = await client.get(api_url, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        direct_url = data.get("stream_url")
                        if direct_url:
                            # Test if the URL is streamable by our IP (no 403 Forbidden)
                            try:
                                head_resp = await client.head(direct_url, follow_redirects=True, timeout=3)
                                is_streamable = head_resp.status_code in (200, 206)
                                if is_streamable:
                                    print(f"[YouTube.video] Synczen direct stream successful: {direct_url[:80]}...")
                                else:
                                    print(f"[YouTube.video] Synczen URL gave {head_resp.status_code}, falling back to download.")
                                return (direct_url, is_streamable)
                            except Exception as test_err:
                                print(f"[YouTube.video] Synczen URL stream test failed ({test_err}), falling back to download.")
                                return (direct_url, False) # Download fallback
            except Exception as e:
                print(f"[YouTube.video] Synczen API failed: {e}")
            return None

        async def try_bxyt():
            """bxyt stream worker — direct proxy streaming."""
            try:
                stream_worker = config.STREAM_WORKER_URL
                if not stream_worker:
                    return None
                import urllib.parse
                encoded_link = urllib.parse.quote_plus(link)
                stream_type = "video" if is_video else "audio"
                worker_url = f"{stream_worker}?type={stream_type}&url={encoded_link}"
                async with await _http_client() as client:
                    resp = await client.head(worker_url, follow_redirects=True, timeout=6)
                    if resp.status_code in (200, 206):
                        print(f"[YouTube.video] bxyt worker resolved: {worker_url[:80]}...")
                        return (worker_url, True)  # Worker proxies are directly streamable
            except Exception as e:
                print(f"[YouTube.video] bxyt worker failed: {e}")
            return None

        # Also try API_URL (honox-style) if it's configured and different from honox
        async def try_api_url():
            """Generic API_URL fallback (same format as honox)."""
            api_base = config.API_URL
            if not api_base or "honox" in api_base:
                return None  # Skip if same as honox
            try:
                if is_video:
                    api_url = f"{api_base}/download?id={video_id}&format=720"
                else:
                    api_url = f"{api_base}/mp3?id={video_id}"
                async with await _http_client() as client:
                    resp = await client.get(api_url, timeout=8)
                    if resp.status_code == 200:
                        data = resp.json()
                        direct_url = data.get("downloadUrl") or data.get("download_url") or data.get("url")
                        if direct_url:
                            print(f"[YouTube.video] API_URL resolved: {direct_url[:80]}...")
                            streamable = "googlevideo.com" in direct_url
                            return (direct_url, streamable)
            except Exception as e:
                print(f"[YouTube.video] API_URL failed: {e}")
            return None

        # Phase 1: Run all resolvers concurrently
        tasks = [
            asyncio.create_task(try_utube_ecru()),   # Priority: googlevideo URLs
            asyncio.create_task(try_honox()),         # CDN/googlevideo URLs
            asyncio.create_task(try_cobalt()),        # Tunnel/CDN URLs
            asyncio.create_task(try_bxyt()),          # Worker proxy
            asyncio.create_task(try_api_url()),       # Generic fallback
        ]
        
        streamable_url = None
        download_urls = []
        
        try:
            # We want to get the first streamable URL quickly.
            # If we get a download URL, we give the other tasks a small grace period (2 seconds)
            # to return a streamable URL before we fallback to downloading.
            pending = set(tasks)
            grace_period_started = False
            grace_end_time = 0
            
            while pending:
                timeout = 15.0
                if grace_period_started:
                    timeout = max(0.1, grace_end_time - time.time())
                
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=timeout)
                
                if not done:
                    # Timeout reached
                    break
                    
                for t in done:
                    try:
                        result = t.result()
                    except Exception as e:
                        print(f"[YouTube.video] Task raised exception: {e}")
                        continue
                        
                    if result:
                        url, is_streamable = result
                        if is_streamable:
                            # Found a directly streamable URL — use it immediately
                            for p in pending:
                                p.cancel()
                            _STREAM_CACHE[video_id] = (time.time(), url)
                            return 1, url
                        else:
                            # Save all download-only URLs
                            if url not in download_urls:
                                download_urls.append(url)
                            
                            # Determine if we have a highly reliable download source (Honox/savetube)
                            has_reliable = any("savetube" in u or "space" in u or "honox" in u for u in download_urls)
                            
                            # Dynamic grace period: 
                            # If we have a reliable URL, we only need a short grace period (1.5s).
                            # If we only have unreliable URLs (like Cobalt tunnels), we wait up to 5.0s
                            # to give reliable sources like Honox a chance to complete.
                            grace_len = 1.5 if has_reliable else 5.0
                            
                            if not grace_period_started:
                                grace_period_started = True
                                grace_end_time = time.time() + grace_len
                            else:
                                # Update grace end time if we just got a reliable URL
                                grace_end_time = min(grace_end_time, time.time() + grace_len)

        except Exception as e:
            print(f"[YouTube.video] Concurrent API resolving error: {e}")
            
        # Ensure all tasks are cleaned up
        for t in pending:
            t.cancel()

        # Phase 2: If we have download URLs but no streamable URL,
        # try downloading from each resolved URL until one succeeds.
        if download_urls:
            local_path = None
            for durl in download_urls:
                print(f"[YouTube.video] No streamable URL found. Trying to download from: {durl[:80]}...")
                try:
                    ext = "mp4" if is_video else "mp3"
                    local_path = f"{DOWNLOAD_DIR}/{video_id}.{ext}"
                    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                    
                    # If file already exists and is large enough, just use it
                    if os.path.exists(local_path) and os.path.getsize(local_path) > 10240:
                        print(f"[YouTube.video] Using existing valid file: {local_path}")
                        return 2, local_path
                        
                    async with await _http_client() as client:
                        async with client.stream("GET", durl, timeout=60) as resp:
                            if resp.status_code == 200:
                                async with aiofiles.open(local_path, "wb") as f:
                                    async for chunk in resp.aiter_bytes(CHUNK_SIZE):
                                        if chunk:
                                            await f.write(chunk)
                            else:
                                print(f"[YouTube.video] Download HTTP error {resp.status_code} for: {durl[:80]}")
                                continue
                                
                    if os.path.exists(local_path) and os.path.getsize(local_path) > 10240:
                        print(f"[YouTube.video] Downloaded successfully: {local_path} ({os.path.getsize(local_path)} bytes)")
                        return 2, local_path
                    else:
                        size_str = f"{os.path.getsize(local_path)} bytes" if os.path.exists(local_path) else "file missing"
                        print(f"[YouTube.video] Download too small or failed ({size_str}) from: {durl[:80]}")
                        # Clean up failed download file
                        if os.path.exists(local_path):
                            try:
                                os.remove(local_path)
                            except Exception:
                                pass
                except Exception as e:
                    print(f"[YouTube.video] Download from {durl[:50]} failed: {e}")
                    if local_path and os.path.exists(local_path):
                        try:
                            os.remove(local_path)
                        except Exception:
                            pass
        
        # Phase 3: Search by title fallback
        # If all direct resolvers failed, search by song title using our intelligent search
        # and try resolving the found alternate video ID.
        if title:
            print(f"[YouTube.video] Direct resolve failed. Trying search fallback for: {title}")
            try:
                alt_info = await self._fetch_video_info(title)
                if alt_info:
                    alt_id = alt_info.get("id")
                    if alt_id and alt_id != video_id:
                        print(f"[YouTube.video] Search fallback found intelligent alternate ID: {alt_id}")
                        # Recursively call video() with the new ID, passing title=None to prevent infinite loops
                        return await self.video(alt_id, is_video=is_video, title=None)
                    else:
                        print(f"[YouTube.video] Search fallback returned same ID or none: {alt_id}")
                else:
                    print(f"[YouTube.video] Search fallback found no results for: {title}")
            except Exception as e:
                print(f"[YouTube.video] Search fallback failed: {e}")
        
        print(f"[YouTube.video] All methods failed for {video_id}")
        return 0, ""

    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = link.split("&")[0]
        if limit <= 0:
            limit = 1
        if limit > 500:
            limit = 500
        stdout, _ = await _exec_proc(
            "yt-dlp",
            "--quiet",
            "--no-warnings",
            *(_cookies_args()),
            "-i",
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--skip-download",
            link,
        )
        if not stdout:
            stdout, _ = await _exec_proc(
                "yt-dlp",
                "--quiet",
                "--no-warnings",
                "-i",
                "--get-id",
                "--flat-playlist",
                "--playlist-end",
                str(limit),
                "--skip-download",
                link,
            )
        items = stdout.decode().strip().split("\n") if stdout else []
        return [i for i in items if i]

    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Track not found")
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        performer = info.get("channel", "YouTube")
        if isinstance(performer, dict):
            performer = performer.get("name", "YouTube")
        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", self._prepare_link(link, videoid)),
            "vidid": info.get("id", ""),
            "duration_min": info.get("duration"),
            "thumb": thumb,
            "performer": str(performer),
        }
        return details, info.get("id", "")

    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        opts = {
            "quiet": True,
            "no_warnings": True,
            "logger": DummyLogger(),
        }
        cf = _cookiefile_path()
        if cf:
            opts["cookiefile"] = cf
        out: List[Dict] = []
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=False)
            for fmt in info.get("formats", []):
                if "dash" in str(fmt.get("format", "")).lower():
                    continue
                if not any(k in fmt for k in ("filesize", "filesize_approx")):
                    continue
                if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")):
                    continue
                size = fmt.get("filesize") or fmt.get("filesize_approx")
                if not size:
                    continue
                out.append(
                    {
                        "format": fmt["format"],
                        "filesize": size,
                        "format_id": fmt["format_id"],
                        "ext": fmt["ext"],
                        "format_note": fmt["format_note"],
                        "yturl": link,
                    }
                )
        return out, link

    async def get_recommendations(self, videoid: str) -> List[Dict]:
        try:
            results = await Recommendations.get(videoid)
            out = []
            for r in results:
                if r.get("type") == "video":
                    out.append({
                        "title": r.get("title"),
                        "id": r.get("id"),
                        "link": r.get("link"),
                        "duration": r.get("duration"),
                        "thumb": r.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
                        "thumbnails": r.get("thumbnails"),
                    })
            return out
        except Exception:
            return []

    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(f"Query type index {query_type} out of range (found {len(results)} results)")
        r = results[query_type]
        return (
            r.get("title", ""),
            r.get("duration"),
            r.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
            r.get("id", ""),
        )

    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None,
        songvideo: Union[bool, str, None] = None,
        format_id: Union[bool, str, None] = None,
        title: Union[bool, str, None] = None,
        duration_sec: int = 0,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        link = self._prepare_link(link, videoid)

        if songvideo:
            p = await download_song_video(link, format_id, title)
            return (p, True) if p else (None, None)

        if songaudio:
            p = await download_song_audio(link, format_id, title)
            return (p, True) if p else (None, None)

        if video:
            if await self.is_live(link):
                status, stream_url = await self.video(link)
                if status == 1:
                    return stream_url, None
                raise ValueError("Unable to fetch live stream link")
            p = await download_video(link, quality=360)
            return (p, True) if p else (None, None)

        # Ensure title is a string if it was passed as True/False
        if not isinstance(title, str):
            title = None

        p = await download_audio(link, title=title, duration_sec=duration_sec)
        return (p, True) if p else (None, None)
