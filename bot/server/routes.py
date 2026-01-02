import math
import logging
from aiohttp import web
from bot import bot, Var
from bot.core.database import db
from urllib.parse import quote 

# FileStreamBot-style helpers
from bot.utils.custom_dl import ByteStreamer
from bot.utils.file_properties import get_file_id_for_stream

logging.getLogger("pyrogram").setLevel(logging.CRITICAL)

routes = web.RouteTableDef()
TG_CHUNK = 1024 * 1024  # 1MB Chunk Size

# ======================================================
# CORS HEADERS (For Player Support)
# ======================================================
def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "Range, Content-Type, User-Agent",
        "Access-Control-Expose-Headers": "Content-Length, Content-Range",
        "Access-Control-Max-Age": "86400",
    }

# 🔥 FIXED: এই ফাংশনটি মিসিং ছিল, তাই এরর আসছিল
def setup_cors(app):
    pass

async def options_handler(request):
    return web.Response(status=204, headers=cors_headers())

# ======================================================
# WATCH PAGE (Simple HTML Player)
# ======================================================
@routes.get("/watch/{id}", allow_head=True)
async def watch_handler(request):
    fid = request.match_info["id"]
    dl_url = f"/dl/{fid}" # Relative URL to avoid mixed content issues

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AnimeToki Player</title>
        <style>
            body {{
                margin: 0;
                background: #000;
                height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                overflow: hidden;
            }}
            video {{
                width: 100%;
                height: 100%;
                max-height: 100vh;
                object-fit: contain; 
            }}
        </style>
    </head>
    <body>
        <video controls autoplay playsinline preload="auto">
            <source src="{dl_url}" type="video/mp4">
            Your browser does not support HTML5 video.
        </video>
    </body>
    </html>
    """

    return web.Response(
        text=html,
        content_type="text/html",
        headers=cors_headers()
    )

# ======================================================
# DOWNLOAD / STREAM HANDLER (FINAL FIX)
# ======================================================
@routes.get("/dl/{id}", allow_head=True)
async def download_handler(request):
    try:
        fid = request.match_info["id"]
        file_data = await db.get_file(fid)
        if not file_data:
            raise web.HTTPNotFound(text="File not found")

        msg_id = int(file_data.get("message_id") or file_data.get("file_id"))
        msg = await bot.get_messages(Var.FILE_STORE, msg_id)

        media = msg.video or msg.document or msg.audio or msg.animation
        if not media:
            raise web.HTTPNotFound(text="Media not found")

        file_id = await get_file_id_for_stream(media)
        file_size = file_id.file_size

        # ==========================================
        # 🔥 PERFECT FILENAME LOGIC START 🔥
        # ==========================================
        file_name = None

        # 1. Document হলে অরিজিনাল নাম
        if msg.document and getattr(msg.document, "file_name", None):
            file_name = msg.document.file_name

        # 2. Video হলে যদি নাম থাকে
        elif msg.video and getattr(msg.video, "file_name", None):
            file_name = msg.video.file_name

        # 3. Audio হলে
        elif msg.audio and getattr(msg.audio, "file_name", None):
            file_name = msg.audio.file_name
        
        # 4. নাম না পেলে Caption থেকে নাম জেনারেট করা
        if not file_name and msg.caption:
            caption_line = msg.caption.split("\n")[0].strip()
            # শুধু ইংরেজি অক্ষর, সংখ্যা এবং স্পেস রাখা হবে
            clean_name = "".join(c for c in caption_line if c.isalnum() or c in " .-_")
            
            # এক্সটেনশন চেক
            mime = getattr(media, "mime_type", "video/mp4")
            ext = "mkv" if "x-matroska" in mime else "mp4"
            
            if not clean_name.lower().endswith(f".{ext}"):
                clean_name += f".{ext}"
            
            file_name = clean_name

        # 5. তাও না পেলে ডিফল্ট নাম
        if not file_name:
            file_name = f"AnimeToki_Video_{fid}.mp4"

        # URL Encoding (To handle spaces and special chars safely)
        encoded_file_name = quote(file_name)
        # ==========================================
        # 🔥 FILENAME LOGIC END 🔥
        # ==========================================

        mime_type = getattr(media, "mime_type", "video/mp4") or "video/mp4"
        range_header = request.headers.get("Range")

        # Range Header Handling
        if range_header:
            try:
                start, end = range_header.replace("bytes=", "").split("-")
                start = int(start)
                end = int(end) if end else file_size - 1
                status = 206
            except ValueError:
                start = 0
                end = file_size - 1
                status = 200
        else:
            start = 0
            end = file_size - 1
            status = 200

        if start >= file_size:
            return web.Response(
                status=416,
                headers={"Content-Range": f"bytes */{file_size}"}
            )

        # Offset Calculation for Telegram
        offset = start - (start % TG_CHUNK)
        first_part_cut = start - offset
        last_part_cut = end % TG_CHUNK + 1
        part_count = (
            math.ceil(end / TG_CHUNK)
            - math.floor(offset / TG_CHUNK)
        )

        streamer = ByteStreamer(bot)
        body = streamer.yield_file(
            file_id,
            offset,
            first_part_cut,
            last_part_cut,
            part_count,
        )

        headers = {
            "Content-Type": mime_type,
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'attachment; filename="{file_name}"; filename*=UTF-8\'\'{encoded_file_name}',
            "Content-Length": str(end - start + 1),
        }
        headers.update(cors_headers())

        if status == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

        return web.Response(
            status=status,
            body=body,
            headers=headers
        )
    except Exception as e:
        print(f"Download Error: {e}")
        raise web.HTTPInternalServerError()

# ======================================================
# ROOT ROUTE
# ======================================================
@routes.get("/")
async def root(request):
    return web.json_response({"status": "running"}, headers=cors_headers())

# ======================================================
# APP SETUP
# ======================================================
def setup(app: web.Application):
    app.router.add_routes(routes)
    app.router.add_route("OPTIONS", "/{tail:.*}", options_handler)
