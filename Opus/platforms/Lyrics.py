import httpx
import syncedlyrics
import logging
from config import LYRICS_API_URL, APEXI_LYRICS_API, VORTEX_API_URL


logging.getLogger("syncedlyrics").setLevel(logging.ERROR)

class LyricsAPI:
    def __init__(self):
        self.elite_api = LYRICS_API_URL
        self.apexi_api = APEXI_LYRICS_API
        self.vortex_api = VORTEX_API_URL

    def _is_mostly_unicode(self, text: str) -> bool:
        if not text:
            return False

        unicode_count = sum(1 for c in text if ord(c) > 127)
        return (unicode_count / len(text)) > 0.3

    def _clean_for_search(self, query: str) -> str:
        if not query:
            return ""
        import re

        clean = re.sub(r"\(.*?\)|\[.*?\]", "", query)
        
        for delim in ["|", "-", ":", "❞", "❝"]:
            if delim in clean:
                clean = clean.split(delim)[0]
        
        clean = re.sub(r'[\|:\-\(\)\[\]❞❝〝〞〟‟♪♫♬♩📻🎶🎧✨🔥💥]', ' ', clean)
        
        # Keep Latin alphabetic, Hindi Devanagari (\u0900-\u097F), spaces and numbers
        cleaned_chars = []
        for c in clean:
            o = ord(c)
            if o < 128 or (0x0900 <= o <= 0x097F) or c.isalnum() or c.isspace():
                cleaned_chars.append(c)
        clean = "".join(cleaned_chars)
        
        clean = re.sub(r"\s+", " ", clean).strip()
        
        if len(clean) < 3:
            return ""
            
        return clean

    async def get_lyrics(self, query):
        if not query or not self.elite_api:
            return None
            
        import re
        query_clean = re.sub(r'[\|]+$', '', query).strip()
        noise_tags = [
            r"\(.*?remix.*?\)", r"\[.*?remix.*?\]", 
            r"\(.*?full song.*?\)", r"\[.*?full song.*?\]",
            r"\(.*?video song.*?\)", r"\[.*?video song.*?\]",
            r"\(.*?lyrical.*?\)", r"\[.*?lyrical.*?\]",
            r"\(.*?official.*?\)", r"\[.*?official.*?\]",
            r"\(.*?audio.*?\)", r"\[.*?audio.*?\]",
            r"\(.*?8d.*?\)", r"\[.*?8d.*?\]",
            r"remix", r"full song", r"lyrical video", r"video song"
        ]
        
        for tag in noise_tags:
            query_clean = re.sub(tag, "", query_clean, flags=re.IGNORECASE)
            
        query_clean = re.sub(r'[\|:\-\(\)\[\]❞❝〝〞〟‟♪♫♬♩📻🎶🎧✨🔥💥]', ' ', query_clean)
        query_clean = re.sub(r'\s+', ' ', query_clean).strip()
        
        try:

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.elite_api.split('?')[0]}?query={query_clean}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    raw_lyrics = data.get("lyrics") or (data.get("data", {}).get("lyrics") if isinstance(data.get("data"), dict) else None)
                    
                    if isinstance(raw_lyrics, dict):
                        lyrics = raw_lyrics.get("lyrics")
                    else:
                        lyrics = raw_lyrics
                        
                    if isinstance(lyrics, str) and len(lyrics) > 50:
                        return lyrics
        except Exception as e:
            print(f"Elite Jio Lyrics Error: {e}")
            
        return None

    async def get_synced_lyrics(self, query):
        if not query:
            return None
            
        clean_q = self._clean_for_search(query)
        

        if self._is_mostly_unicode(query) or not clean_q:
            if self.vortex_api:
                try:
                    import urllib.parse
                    encoded_q = urllib.parse.quote(query)

                    base_url = self.vortex_api.rstrip("/")
                    if not base_url.endswith("/api"):
                        url = f"{base_url}/api/search?query={encoded_q}"
                    else:
                        url = f"{base_url}/search?query={encoded_q}"
                        
                    async with httpx.AsyncClient() as client:
                        v_resp = await client.get(url, timeout=5)
                        if v_resp.status_code == 200:
                            v_data = v_resp.json()
                            results = v_data.get("data", {}).get("songs", {}).get("results", [])
                            if results:

                                for r in results[:5]:
                                    v_title = r.get("title")
                                    if v_title and not self._is_mostly_unicode(v_title):
                                        clean_q = v_title
                                        break
                except Exception as e:
                    pass


        if not clean_q or not any(c.isalpha() for c in clean_q):
             clean_q = query
             

        # Try Ryzen-Lrc APIs first for high-fidelity synced lyrics
        try:
            import urllib.parse
            encoded_q = urllib.parse.quote(clean_q)
            
            # 1. Try standard Ryzen-Lrc endpoint (lrclib)
            async with httpx.AsyncClient() as client:
                ryzen_url = f"https://ryzen-lrc.vercel.app/lyrics?q={encoded_q}"
                resp = await client.get(ryzen_url, timeout=7)
                if resp.status_code == 200:
                    data = resp.json()
                    lrc_text = data.get("synced_lyrics")
                    if lrc_text:
                        parsed = self.parse_synced_lyrics(lrc_text)
                        if parsed:
                            return parsed
                            
            # 2. Try Ryzen-Lrc Musixmatch fallback endpoint
            async with httpx.AsyncClient() as client:
                ryzen_mm_url = f"https://ryzen-lrc.vercel.app/lyrics/musixmatch?q={encoded_q}"
                resp = await client.get(ryzen_mm_url, timeout=7)
                if resp.status_code == 200:
                    data = resp.json()
                    lrc_text = data.get("synced_lyrics")
                    if lrc_text:
                        parsed = self.parse_synced_lyrics(lrc_text)
                        if parsed:
                            return parsed
        except Exception as e:
            print(f"Ryzen LRC API Error: {e}")

        try:
            import asyncio
            loop = asyncio.get_event_loop()
            lrc_text = await loop.run_in_executor(None, syncedlyrics.search, clean_q)
            if lrc_text:
                parsed = self.parse_synced_lyrics(lrc_text)
                if parsed:
                    return parsed
        except Exception as e:
            print(f"SyncedLyrics Module Error: {e}")


        if self.apexi_api:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{self.apexi_api}{clean_q}", timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        tracks = data.get("data", [])
                        if tracks:
                            lrc_text = tracks[0].get("syncedLyrics")
                            if lrc_text:
                                parsed = self.parse_synced_lyrics(lrc_text)
                                if parsed:
                                    return parsed
            except Exception as e:
                print(f"Apexi Synced Lyrics Error: {e}")


        try:
            lyrics = await self.get_lyrics(query)
            if lyrics and "no lyrics available" not in lyrics.lower():

                return lyrics
        except:
            pass
            
        return None

    def parse_synced_lyrics(self, lrc_text):
        if not lrc_text or not isinstance(lrc_text, str):
            return None
        
        import re
        lines = []

        pattern = re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)')
        
        for line in lrc_text.split('\n'):
            match = pattern.match(line.strip())
            if match:
                try:
                    minutes = int(match.group(1))
                    seconds = float(match.group(2))
                    text = match.group(3).strip()
                    total_seconds = minutes * 60 + seconds

                    if text:
                        lines.append((total_seconds, text))
                except:
                    continue
        
        return sorted(lines, key=lambda x: x[0]) if lines else None

Lyrics = LyricsAPI()
