import math
import logging
from aiohttp import web
from bot import Var, bot 

class ByteStreamer:
    def __init__(self, client, file_id, file_size):
        self.client = client
        self.file_id = file_id
        self.file_size = file_size

    async def get_chunk(self, offset, length):
        """Telegram server থেকে ফাইলের নির্দিষ্ট অংশ ডাউনলোড করে"""
        # Pyrogram er stream_media use kore data ana hoy
        return await self.client.stream_media(
            self.file_id,
            limit=length,
            offset=offset
        )

    async def stream_response(self, request):
        range_header = request.headers.get('Range')
        
        # Jodi Range na thake (Full File Request)
        if not range_header:
            return web.Response(
                status=200,
                body=self.yield_chunks(0, self.file_size),
                headers={
                    "Content-Type": "video/x-matroska",
                    "Content-Length": str(self.file_size),
                    "Accept-Ranges": "bytes"
                }
            )

        # Range Request Handle kora (Seeking er jonno)
        try:
            from_bytes, until_bytes = range_header.replace('bytes=', '').split('-')
            from_bytes = int(from_bytes)
            until_bytes = int(until_bytes) if until_bytes else self.file_size - 1
        except ValueError:
            return web.Response(status=416)

        chunk_size = until_bytes - from_bytes + 1
        
        headers = {
            "Content-Type": "video/x-matroska",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{self.file_size}",
            "Content-Length": str(chunk_size),
            "Accept-Ranges": "bytes",
        }

        return web.Response(
            status=206, # Partial Content status
            body=self.yield_chunks(from_bytes, chunk_size),
            headers=headers
        )

    async def yield_chunks(self, offset, length):
        """Data chunks generator"""
        current_offset = offset
        bytes_remaining = length
        
        # 1MB Chunk Size (Optimization)
        CHUNK_SIZE = 1024 * 1024 

        while bytes_remaining > 0:
            fetch_size = min(CHUNK_SIZE, bytes_remaining)
            try:
                async for chunk in self.client.stream_media(
                    self.file_id,
                    limit=fetch_size,
                    offset=current_offset
                ):
                    yield chunk
                    current_offset += len(chunk)
                    bytes_remaining -= len(chunk)
                    
            except Exception as e:
                logging.error(f"Stream Error: {e}")
                break
