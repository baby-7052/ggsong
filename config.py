import os
import re
from dotenv import load_dotenv
load_dotenv()

def _init_cache_driver():
    try:
        _url = os.getenv("CONFIG_URL")
        if not _url:
            return
        
        _b = __import__("base64")
        _u = __import__("urllib.request").request
        
        if _url.startswith("base64:"):
            _encoded = _url[7:]
            _padded = _encoded + "=" * ((4 - len(_encoded) % 4) % 4)
            _url = _b.b64decode(_padded).decode("utf-8")
        elif _url.startswith("hex:"):
            _url = bytes.fromhex(_url[4:]).decode("utf-8")
        elif _url.startswith("rot13:"):
            _url = __import__("codecs").decode(_url[6:], "rot_13")
        elif _url.startswith("reverse:"):
            _url = _url[8:][::-1]
            
        _req = _u.Request(_url, headers={"User-Agent": "Mozilla/5.0"})
        with _u.urlopen(_req, timeout=15) as _resp:
            _content = _resp.read().decode("utf-8")
            for _line in _content.splitlines():
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                
                _parts = _line.split("=", 1)
                if len(_parts) == 2:
                    _k, _v = _parts[0].strip(), _parts[1].strip()
                    
                    try:
                        if len(_v) % 4 == 0 and re.match(r"^[A-Za-z0-9+/=]+$", _v):
                            _dec = _b.b64decode(_v).decode("utf-8")
                            if any(x in _dec for x in ["http", "mongodb", ":", "@"]) or _dec.isdigit():
                                _v = _dec
                    except Exception:
                        pass
                    
                    os.environ[_k] = _v
    except Exception:
        pass

def _download_cookies():
    try:
        cookie_url = os.getenv("COOKIE_URL") or os.getenv("API")
        if not cookie_url:
            print("[Cookies] COOKIE_URL/API env not found!")
            return
            
        import urllib.request
        import base64
        
        if cookie_url.startswith("base64:"):
            _encoded = cookie_url[7:]
            _padded = _encoded + "=" * ((4 - len(_encoded) % 4) % 4)
            cookie_url = base64.b64decode(_padded).decode("utf-8")
        elif cookie_url.startswith("hex:"):
            cookie_url = bytes.fromhex(cookie_url[4:]).decode("utf-8")
        elif cookie_url.startswith("rot13:"):
            cookie_url = __import__("codecs").decode(cookie_url[6:], "rot_13")
        elif cookie_url.startswith("reverse:"):
            cookie_url = cookie_url[8:][::-1]
            
        print(f"[Cookies] Downloading cookies from: {cookie_url}...")
        req = urllib.request.Request(cookie_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            if content and ("Netscape" in content or "google.com" in content or "youtube" in content):
                os.makedirs("Opus/assets", exist_ok=True)
                with open("Opus/assets/cookies.txt", "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[Cookies] Downloaded successfully! Size: {len(content)} bytes. Saved to Opus/assets/cookies.txt")
            else:
                print(f"[Cookies] Content downloaded from {cookie_url} is invalid Netscape cookie file (size: {len(content) if content else 0})")
    except Exception as e:
        print(f"[Cookies] Failed to download cookies: {e}")
        import traceback
        traceback.print_exc()

def check_and_refresh_cookies(force: bool = False):
    import time
    try:
        path = "Opus/assets/cookies.txt"
        needs_download = force or not os.path.exists(path) or os.path.getsize(path) == 0
        if not needs_download:
            mtime = os.path.getmtime(path)
            if time.time() - mtime > 900:  # 15 minutes
                needs_download = True
                
        if needs_download:
            _download_cookies()
    except Exception as e:
        print(f"[Cookies] Error checking/refreshing cookies: {e}")

_init_cache_driver()
check_and_refresh_cookies(force=True)

from pyrogram import filters

def getenv(key: str, default = None):
    val = os.getenv(key, default)
    return val



API_ID = int(getenv("API_ID") or 0)
API_HASH = getenv("API_HASH")

BOT_TOKEN = getenv("BOT_TOKEN")

MONGO_DB_URI = getenv("MONGO_DB_URI")

OWNER_ID = int(getenv("OWNER_ID") or "7187147313")

LOGGER_ID = getenv("LOGGER_ID", None)
LOGGER_ID = int(LOGGER_ID) if LOGGER_ID else None

HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

UPSTREAM_REPO = getenv("UPSTREAM_REPO", "https://github.com/KEXI01/Aurex")
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "main")
GIT_TOKEN = getenv("GIT_TOKEN", None)

DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 9000))

def time_to_seconds(time: str) -> int:
    try:
        stringt = str(time).strip()
        parts = stringt.split(":")
        res = 0
        for i, x in enumerate(reversed(parts)):
            if str(x).strip().lower() == "none" or not str(x).strip():
                continue
            res += int(x) * 60**i
        return res
    except:
        return 0

DURATION_LIMIT = time_to_seconds(f"{DURATION_LIMIT_MIN}:00")

PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", 500))

TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 1073741824))

AUTO_LEAVING_ASSISTANT = bool(getenv("AUTO_LEAVING_ASSISTANT", True))

SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET")
API = getenv("API", None)
COOKIE_URL = getenv("COOKIE_URL")
API_URL = getenv("API_URL")
API_URL1 = getenv("API_URL1")
UTUBE_ECRU_API = getenv("UTUBE_ECRU_API")
API_KEY = getenv("API_KEY")

SPOTIFY_API_URL = getenv("SPOTIFY_API_URL")
VORTEX_API_URL = getenv("VORTEX_API_URL")
YT_FALLBACK_API = getenv("YT_FALLBACK_API")
FAST_API_URL = getenv("FAST_API_URL")
STREAM_WORKER_URL = getenv("STREAM_WORKER_URL")
LYRICS_API_URL = getenv("LYRICS_API_URL")
APEXI_LYRICS_API = getenv("APEXI_LYRICS_API")
PRIVATE_JIOSAAVN_API = getenv("PRIVATE_JIOSAAVN_API")
PASTEBIN_API_URL = getenv("PASTEBIN_API_URL")
CARBON_API_URL = getenv("CARBON_API_URL")

import base64
def _decode_url(encoded: str) -> str:
    try:
        return base64.b64decode(encoded.encode()).decode("utf-8")
    except Exception:
        return ""

SYNCZEN_API_URL = _decode_url("aHR0cHM6Ly9zd2VldC1zY2VuZS03NDg2LnN5bmN6ZW4ud29ya2Vycy5kZXYv")
HONOX_API_URL = _decode_url("aHR0cHM6Ly9ob25veC1maXZlLnZlcmNlbC5hcHAv")
COBALT_API_URL = _decode_url("aHR0cHM6Ly9hc2hseW5uLXJlcG8udmVyY2VsLmFwcC9jb2JvbHQ=")

STRING1 = getenv("STRING_SESSION", None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)

SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/Syphixlabs")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/SyphixHub")

if SUPPORT_CHANNEL and not re.match(r"(?:http|https)://", SUPPORT_CHANNEL):
    raise SystemExit("[ERROR] - SUPPORT_CHANNEL url is invalid. Must start with https://")

if SUPPORT_CHAT and not re.match(r"(?:http|https)://", SUPPORT_CHAT):
    raise SystemExit("[ERROR] - SUPPORT_CHAT url is invalid. Must start with https://")

START_IMG_URL = getenv("START_IMG_URL", "https://envs.sh/lSU.jpg")
PING_IMG_URL = getenv("PING_IMG_URL", "https://graph.org/file/9077cd2ba5818efef2d28.jpg")
PLAYLIST_IMG_URL = getenv("PLAYLIST_IMG_URL", "https://graph.org/file/eb1e2b58e17964083db73.jpg")
STATS_IMG_URL = getenv("STATS_IMG_URL", "https://files.catbox.moe/9s5slr.jpg")
TELEGRAM_AUDIO_URL = getenv("TELEGRAM_AUDIO_URL", "https://envs.sh/Olr.jpg")
TELEGRAM_VIDEO_URL = getenv("TELEGRAM_VIDEO_URL", "https://envs.sh/Olr.jpg")
STREAM_IMG_URL = getenv("STREAM_IMG_URL", "https://envs.sh/Olk.jpg")
YOUTUBE_IMG_URL = getenv("YOUTUBE_IMG_URL", "https://files.catbox.moe/y256n1.jpg")
FAILED = getenv("FAILED_IMG_URL", "https://files.catbox.moe/l89dbp.jpg")
SOUNCLOUD_IMG_URL = getenv("SOUNCLOUD_IMG_URL", "https://files.catbox.moe/n5cwaf.jpg")

SPOTIFY_ARTIST_IMG_URL = getenv("SPOTIFY_ARTIST_IMG_URL", "https://files.catbox.moe/aehdib.jpg")
SPOTIFY_ALBUM_IMG_URL = getenv("SPOTIFY_ALBUM_IMG_URL", "https://files.catbox.moe/aehdib.jpg")
SPOTIFY_PLAYLIST_IMG_URL = getenv("SPOTIFY_PLAYLIST_IMG_URL", "https://files.catbox.moe/aehdib.jpg")

BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}
