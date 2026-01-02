import asyncio
import logging
from typing import Dict, Union
from pyrogram import raw, utils
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from bot import bot

TG_CHUNK = 1024 * 1024

class ByteStreamer:
    def __init__(self, client):
        self.client = client
        self.cached_file_ids: Dict[str, FileId] = {}

    async def generate_media_session(self, client, file_id: FileId) -> Session:
        media_session = client.media_sessions.get(file_id.dc_id)

        if media_session:
            return media_session

        if file_id.dc_id != await client.storage.dc_id():
            media_session = Session(
                client,
                file_id.dc_id,
                await Auth(client, file_id.dc_id, await client.storage.test_mode()).create(),
                await client.storage.test_mode(),
                is_media=True,
            )
            await media_session.start()

            for _ in range(5):
                exported = await client.invoke(
                    raw.functions.auth.ExportAuthorization(dc_id=file_id.dc_id)
                )
                try:
                    await media_session.invoke(
                        raw.functions.auth.ImportAuthorization(
                            id=exported.id,
                            bytes=exported.bytes
                        )
                    )
                    break
                except AuthBytesInvalid:
                    continue
        else:
            media_session = Session(
                client,
                file_id.dc_id,
                await client.storage.auth_key(),
                await client.storage.test_mode(),
                is_media=True,
            )
            await media_session.start()

        client.media_sessions[file_id.dc_id] = media_session
        return media_session

    async def get_location(self, file_id: FileId):
        if file_id.file_type == FileType.PHOTO:
            return raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        return raw.types.InputDocumentFileLocation(
            id=file_id.media_id,
            access_hash=file_id.access_hash,
            file_reference=file_id.file_reference,
            thumb_size=file_id.thumbnail_size,
        )

    async def yield_file(
        self,
        file_id: FileId,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
    ):
        media_session = await self.generate_media_session(self.client, file_id)
        location = await self.get_location(file_id)

        current = 1
        while True:
            r = await media_session.invoke(
                raw.functions.upload.GetFile(
                    location=location,
                    offset=offset,
                    limit=TG_CHUNK
                )
            )
            if not r.bytes:
                break

            chunk = r.bytes
            if part_count == 1:
                yield chunk[first_part_cut:last_part_cut]
            elif current == 1:
                yield chunk[first_part_cut:]
            elif current == part_count:
                yield chunk[:last_part_cut]
            else:
                yield chunk

            offset += TG_CHUNK
            current += 1
            if current > part_count:
                break
