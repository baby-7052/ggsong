import re
import aiohttp
from youtubesearchpython.future import VideosSearch
from urllib.parse import quote

import config


class SpotifyAPI:
    def __init__(self):
        self.regex = r"^(https:\/\/open.spotify.com\/)(.*)$"
        self.client_id = config.SPOTIFY_CLIENT_ID
        self.client_secret = config.SPOTIFY_CLIENT_SECRET
        self.api = config.SPOTIFY_API_URL

    async def valid(self, link: str):
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def track(self, link: str):
        track_id = link.split("/")[-1].split("?")[0]
        track_details = None
        vidid = track_id
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api}{track_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and data.get("data"):
                        song_data = data["data"]
                        # Handle cases where data might be a single song or search results
                        if "songs" in song_data and song_data["songs"]:
                            song = song_data["songs"][0]
                        else:
                            song = song_data
                        
                        title = song.get("name", "Unknown")
                        artists = song.get("artists", {}).get("primary", [])
                        artist_name = ", ".join([a["name"] for a in artists]) if artists else "Unknown"
                        
                        # Get high quality image
                        images = song.get("image", [])
                        thumb = None
                        if images:
                            # Prefer 500x500 or the last one (usually highest quality)
                            thumb_obj = next((i for i in images if i.get("quality") == "500x500"), images[-1])
                            thumb = thumb_obj.get("url")
                        
                        # Get high quality audio
                        download_urls = song.get("downloadUrl", [])
                        direct_url = None
                        if download_urls:
                            # Prefer 320kbps or the last one
                            url_obj = next((u for u in download_urls if u.get("quality") == "320kbps"), download_urls[-1])
                            direct_url = url_obj.get("url")
                        
                        duration_sec = song.get("duration", 0)
                        from Opus.utils.formatters import seconds_to_min
                        duration_min = seconds_to_min(duration_sec) if duration_sec else "00:00"
                        
                        track_details = {
                            "title": f"{title} - {artist_name}",
                            "link": link,
                            "vidid": vidid,
                            "duration_min": duration_min,
                            "thumb": thumb,
                            "path": direct_url, # Direct audio link
                        }

        if not track_details:
            # Fallback to YouTube search if API fails
            from youtubesearchpython.future import VideosSearch
            results = VideosSearch(track_id, limit=1)
            video_results = await results.next()
            if video_results and video_results.get("result"):
                result = video_results["result"][0]
                track_details = {
                    "title": result["title"],
                    "link": result["link"],
                    "vidid": result["id"],
                    "duration_min": result["duration"],
                    "thumb": result["thumbnails"][0]["url"].split("?")[0],
                }
            else:
                track_details = {
                    "title": track_id,
                    "link": link,
                    "vidid": f"vortex_{vidid}",
                    "duration_min": "00:00",
                    "thumb": None,
                }
        else:
            # Prefix Spotify IDs for consistent handling in Save/Play callbacks
            track_details["vidid"] = f"vortex_{track_details['vidid']}"
            vidid = track_details["vidid"]
        return track_details, vidid

    async def playlist(self, url):
        playlist_id = url.split("/")[-1].split("?")[0]
        results = []
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api}{playlist_id}", params={"limit": config.PLAYLIST_FETCH_LIMIT}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and data.get("data"):
                        songs = data["data"].get("songs", [])
                        from Opus.utils.formatters import seconds_to_min
                        for song in songs:
                            title = song.get("name", "Unknown")
                            artists = song.get("artists", {}).get("primary", [])
                            artist_name = ", ".join([a["name"] for a in artists]) if artists else "Unknown"
                            
                            images = song.get("image", [])
                            thumb = images[-1].get("url") if images else None
                            
                            download_urls = song.get("downloadUrl", [])
                            direct_url = download_urls[-1].get("url") if download_urls else None
                            
                            duration_sec = song.get("duration", 0)
                            duration_min = seconds_to_min(duration_sec) if duration_sec else "00:00"
                            
                            results.append({
                                "title": f"{title} - {artist_name}",
                                "thumb": thumb,
                                "duration_min": duration_min,
                                "duration_sec": duration_sec,
                                "vidid": f"vortex_{song.get('id')}",
                                "path": direct_url,
                            })
        return results, playlist_id

    async def album(self, url):
        # The new API likely handles albums the same way as playlists (by ID)
        return await self.playlist(url)

    async def artist(self, url):
        # Same as playlist/album for this API
        return await self.playlist(url)
