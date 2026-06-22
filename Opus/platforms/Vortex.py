import httpx
import config
from typing import Dict, List, Optional, Tuple

class VortexAPI:
    def __init__(self) -> None:
        self.base_url = config.VORTEX_API_URL

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{self.base_url}{endpoint}", params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            print(f"[Vortex API] Error at {endpoint}: {e}")
        return None

    async def search(self, query: str) -> List[Dict]:
        data = await self._get("/search", params={"query": query})
        if data and data.get("success"):
            return data["data"].get("songs", {}).get("results", [])
        return []

    async def get_suggestions(self, song_id: str) -> List[Dict]:
        data = await self._get(f"/songs/{song_id}/suggestions")
        if data and data.get("success"):
            return data["data"]
        return []

    async def search_playlists(self, query: str) -> List[Dict]:
        data = await self._get("/search/playlists", params={"query": query})
        if data and data.get("success"):
            return data["data"].get("results", [])
        return []

    async def get_playlist_details(self, playlist_id: str) -> List[Dict]:
        data = await self._get("/playlists", params={"id": playlist_id, "limit": config.PLAYLIST_FETCH_LIMIT})
        if data and data.get("success"):
            songs = data["data"].get("songs", [])
            results = []
            from Opus.utils.formatters import seconds_to_min
            for song in songs:
                download_urls = song.get("downloadUrl", [])
                best_link = download_urls[-1].get("url") if download_urls else None
                images = song.get("image", [])
                thumb = images[-1].get("url") if images else config.YOUTUBE_IMG_URL
                duration = song.get("duration", 0)
                duration_min = seconds_to_min(duration)
                results.append({
                    "title": song.get("name", "Unknown"),
                    "duration_min": duration_min,
                    "duration_sec": duration,
                    "thumb": thumb,
                    "vidid": f"vortex_{song.get('id')}",
                    "path": best_link,
                    "duration_sec": duration,
                })
            return results
        return []

    async def details(self, song_id: str) -> Optional[Dict]:
        data = await self._get(f"/songs/{song_id}")
        if data and data.get("success") and data.get("data"):

            song_list = data["data"]
            if isinstance(song_list, list) and len(song_list) > 0:
                song = song_list[0]

                download_urls = song.get("downloadUrl", [])
                best_link = download_urls[-1].get("url") if download_urls else None
                

                images = song.get("image", [])
                thumb = images[-1].get("url") if images else config.YOUTUBE_IMG_URL
                

                duration = song.get("duration", 0)
                from Opus.utils.formatters import seconds_to_min
                duration_min = seconds_to_min(duration)

                return {
                    "title": song.get("name", "Unknown"),
                    "link": best_link,
                    "vidid": f"vortex_{song.get('id')}",
                    "duration_min": duration_min,
                    "duration_sec": duration,
                    "thumb": thumb,
                    "path": best_link, 
                }
        return None

from os import getenv
