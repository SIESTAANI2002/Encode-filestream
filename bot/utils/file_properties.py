from pyrogram.file_id import FileId
from bot.core.database import db

async def get_file_id_for_stream(msg):
    file_id = FileId.decode(msg.file_id)
    setattr(file_id, "file_size", msg.file_size)
    setattr(file_id, "mime_type", msg.mime_type)
    setattr(file_id, "file_name", msg.file_name or "video.mp4")
    return file_id
