import os
import asyncio
from os import path as ospath
from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, remove as aioremove, mkdir
from aiohttp import ClientSession
from torrentp import TorrentDownloader
from bot.core.func_utils import handle_logs

class TorDownloader:
    def __init__(self, path="./downloads"):
        self.__downdir = path
        self.__torpath = "torrents/"

    @handle_logs
    async def download(self, torrent_url, name=None):
        # 1. Download the .torrent file from URL
        torfile = await self.get_torfile(torrent_url)
        if not torfile:
            print("❌ Failed to download .torrent file")
            return None

        try:
            # 2. Initialize TorrentDownloader
            torp = TorrentDownloader(torfile, self.__downdir)
            
            # 3. Start Download
            # ✅ FIX: Log says it's a coroutine, so we must AWAIT it directly.
            # No need for asyncio.to_thread
            await torp.start_download()
            
            # 4. Clean up .torrent file
            if await aiopath.exists(torfile):
                await aioremove(torfile)

            # 5. Find the downloaded video file
            return await self._find_video_file(name)

        except Exception as e:
            print(f"⚠️ TorrentP Error: {e}")
            # Cleanup on error
            if await aiopath.exists(torfile):
                await aioremove(torfile)
            return None

    async def _find_video_file(self, name):
        """Helper to find the largest video file in downloads folder"""
        target_extensions = ('.mkv', '.mp4', '.avi', '.mov', '.flv')
        
        # Walk through the download directory
        for root, dirs, files in os.walk(self.__downdir):
            for file in files:
                # If a specific name is provided, try to match it
                if name and name in file:
                    return os.path.join(root, file)
                
                # Otherwise, look for video extensions
                if file.lower().endswith(target_extensions):
                    return os.path.join(root, file)
        
        return None

    @handle_logs
    async def get_torfile(self, url):
        if not await aiopath.isdir(self.__torpath):
            await mkdir(self.__torpath)

        # Generate a safe filename
        tor_name = url.split('/')[-1]
        if not tor_name.endswith(".torrent"):
            tor_name += ".torrent"
            
        des_dir = ospath.join(self.__torpath, tor_name)

        try:
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        async with aiopen(des_dir, 'wb') as file:
                            async for chunk in response.content.iter_any():
                                await file.write(chunk)
                        return des_dir
                    else:
                        print(f"❌ .torrent URL Error: Status {response.status}")
                        return None
        except Exception as e:
            print(f"❌ Error fetching .torrent file: {e}")
            return None
