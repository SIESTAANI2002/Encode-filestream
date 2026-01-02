import asyncio
import secrets
import base64
from asyncio import Event
from os import path as ospath
from aiofiles.os import remove as aioremove
from traceback import format_exc
from urllib.parse import quote

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot import bot, bot_loop, Var, ani_cache, ffQueue, ffLock, ff_queued
from .tordownload import TorDownloader
from bot.core.database import db
from .func_utils import getfeed, editMessage, sendMessage, convertBytes
from .text_utils import TextEditor
from .ffencoder import FFEncoder
from .tguploader import TgUploader
from .reporter import rep

btn_formatter = { "1080": "1080p", "720": "720p", "480": "480p" }

# ✅ CONFIG
WEB_HOST = "https://animetoki.com/app"
DIRECT_APP_LINK = "https://t.me/Anime_Toki_bot/Toki" 
STREAM_DOMAIN = "https://stream.animetoki.com/"

async def save_file_to_db(msg, drive_id, r2_link, sub_link, qual, anime_info, extra_meta):
    try:
        file = msg.document or msg.video
        unique_id = secrets.token_urlsafe(8)
        
        doc = {
            '_id': unique_id,
            'file_id': msg.id, 
            'file_unique_id': file.file_unique_id,
            'file_name': file.file_name,
            'file_size': file.file_size,
            'mime_type': "video/mp4",
            'drive_id': drive_id,       
            'stream_link': r2_link,
            'subtitle_link': sub_link,
            'quality': qual,
            'anime_title': anime_info.get('title'),
            'episode': anime_info.get('episode'),
            'poster': anime_info.get('poster'),
            'genres': extra_meta.get('genres'),
            'status': extra_meta.get('status'),
            'audio': extra_meta.get('audio'),
            'subtitle': extra_meta.get('subtitle'),
            'codec': extra_meta.get('codec'),
            'resolution': extra_meta.get('resolution'),
            'timestamp': msg.date
        }
        if hasattr(db, 'files'): await db.files.insert_one(doc)
        else: await db._MongoDB__db.files.insert_one(doc)
        return unique_id
    except Exception as e:
        print(f"DB Save Error: {e}")
        return None

async def fetch_animes():
    await rep.report("Fetch Animes Started !!", "info")
    while True:
        await asyncio.sleep(60)
        if ani_cache.get("fetch_animes"):
            for link in Var.RSS_ITEMS:
                if (info := await getfeed(link, 0)):
                    bot_loop.create_task(get_animes(info.title, info.link))

async def get_animes(name, torrent, force=False):
    ep_key = None
    try:
        aniInfo = TextEditor(name)
        await aniInfo.load_anilist()
        ani_id = aniInfo.adata.get("id")
        ep_no = aniInfo.pdata.get("episode_number")
        ep_key = f"{ani_id}-{ep_no}"

        # 1. Memory Check
        if ep_key in ani_cache.get("completed", set()) and not force: return
        if ep_key in ani_cache.get("ongoing", set()) and not force: return
        
        # 2. Database Check
        chk_title = (aniInfo.adata.get("title", {}).get("english") or aniInfo.adata.get("title", {}).get("romaji") or name)
        db_col = db.files if hasattr(db, 'files') else db._MongoDB__db.files
        is_exist = await db_col.find_one({'anime_title': chk_title, 'episode': ep_no})

        if is_exist and not force:
            print(f"✅ Skipping: {chk_title} - EP {ep_no} (Already in DB)")
            ani_cache.setdefault("completed", set()).add(ep_key)
            return

        ani_cache.setdefault("ongoing", set()).add(ep_key)

        poster = await aniInfo.get_poster()
        caption = await aniInfo.get_caption()
        
        post_msg = await bot.send_photo(Var.MAIN_CHANNEL, photo=poster, caption=caption)
        stat_msg = await sendMessage(Var.MAIN_CHANNEL, f"<b>{name}</b>\n\n<i>Downloading...</i>")

        # ==========================================
        # 🔥 TORRENT RETRY LOGIC (5 TIMES) 🔥
        # ==========================================
        dl = None
        max_retries = 5

        for attempt in range(1, max_retries + 1):
            try:
                dl = await TorDownloader("./downloads").download(torrent, name)
                
                if dl and ospath.exists(dl):
                    break 
                
                if attempt < max_retries:
                    await editMessage(stat_msg, f"<b>{name}</b>\n\n<i>⚠️ Download Failed (Attempt {attempt}/{max_retries})\nRetrying in 10s...</i>")
                    await asyncio.sleep(10)
            except Exception as e:
                print(f"Download Error Attempt {attempt}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(10)

        # 🔥 ৫ বার ফেইল হলে এই মেসেজ দেখাবে 🔥
        if not dl or not ospath.exists(dl):
            fail_text = (
                f"<b>{name}</b>\n\n"
                f"❌ <b>Download Failed!</b>\n"
                f"<i>Tried {max_retries} times but failed to fetch the file.</i>\n\n"
                f"🆘 <b>Contact Admin:</b> @Ani_Animesh"
            )
            await editMessage(stat_msg, fail_text)
            
            # ক্যাশ ক্লিয়ার করা
            ani_cache["ongoing"].discard(ep_key)
            
            # ⚠️ আমি ডিলিট অপশন বন্ধ রেখেছি যাতে আপনি মেসেজটা দেখতে পান
            # await stat_msg.delete() 
            return
        # ==========================================

        ev = Event()
        ff_queued[post_msg.id] = ev
        await ffQueue.put(post_msg.id)
        await ev.wait()
        await ffLock.acquire()
        buttons = []

        for qual in Var.QUALS:
            filename = await aniInfo.get_upname(qual)
            await editMessage(stat_msg, f"<b>{name}</b>\n<i>Encoding {qual}...</i>")
            
            encoder = FFEncoder(stat_msg, dl, filename, qual)
            out_path = await encoder.start_encode()
            sub_path = await encoder.extract_subtitle()

            if not out_path or not ospath.exists(out_path): continue

            await editMessage(stat_msg, f"<b>{name}</b>\n<i>Uploading {qual}...</i>")
            msg, drive_id, r2_link, sub_link = await TgUploader(stat_msg).upload(out_path, qual, sub_path)

            anime_title = (aniInfo.adata.get("title", {}).get("english") or aniInfo.adata.get("title", {}).get("romaji") or name)
            genres = ", ".join(f"#{g}" for g in (aniInfo.adata.get("genres") or []))
            status = aniInfo.adata.get("status", "N/A")
            
            a_info = {'title': anime_title, 'episode': ep_no, 'poster': poster}
            extra_meta = {'genres': genres, 'status': status, 'audio': "Japanese", 'subtitle': "English", 'codec': "HEVC", 'resolution': " | ".join(f"{q}p" for q in Var.QUALS)}
            
            unique_id = await save_file_to_db(msg, drive_id, r2_link, sub_link, qual, a_info, extra_meta)
            btn_text = f"{btn_formatter.get(qual, qual)} • {convertBytes(msg.document.file_size or msg.video.file_size)}"
            
            if unique_id:
                short_r2 = r2_link.replace(STREAM_DOMAIN, "") if r2_link else "0"
                short_sub = sub_link.replace(STREAM_DOMAIN, "") if sub_link else "0"
                
                p_title = anime_title.replace("|", "") 
                p_ep = str(ep_no).replace(" ", "")
                p_size = convertBytes(msg.document.file_size or msg.video.file_size).replace(" ", "")
                p_qual = qual
                p_drive = drive_id if drive_id else "0"
                p_poster = poster if poster else "0"
                p_uid = unique_id 
                
                raw_data = f"{p_title}|{p_ep}|{p_size}|{p_qual}|{p_drive}|{p_poster}|{short_r2}|{short_sub}|{p_uid}"
                final_param = base64.urlsafe_b64encode(raw_data.encode()).decode().rstrip("=")
                safe_param = quote(final_param)
                
                direct_link = f"{DIRECT_APP_LINK}?startapp={safe_param}"
                
                btn = InlineKeyboardButton(text=btn_text, url=direct_link)
                if buttons and len(buttons[-1]) == 1: buttons[-1].append(btn)
                else: buttons.append([btn])

                if Var.LOG_CHANNEL:
                    try:
                        base_url = getattr(Var, "URL", "") or getattr(Var, "HEROKU_APP_URL", "")
                        if base_url: base_url = str(base_url).strip().strip("'").strip('"').strip("/")

                        tg_link = msg.link if msg else "N/A"
                        web_watch = f"{base_url}/watch/{unique_id}" if base_url else "N/A"
                        web_dl = f"{base_url}/dl/{unique_id}" if base_url else "N/A"
                        drive_url = f"https://drive.google.com/file/d/{drive_id}/view" if drive_id else "N/A"
                        
                        log_text = (
                            f"✅ <b>Uploaded:</b> {anime_title}\n"
                            f"✨ <b>Quality:</b> {qual}\n\n"
                            f"✈️ <b>Telegram:</b> <a href='{tg_link}'>Link</a>\n"
                            f"📂 <b>Drive:</b> <a href='{drive_url}'>Link</a>\n"
                            f"▶️ <b>Web Watch:</b> <a href='{web_watch}'>Link</a>\n"
                            f"📥 <b>Web DL:</b> <a href='{web_dl}'>Link</a>\n"
                            f"☁️ <b>R2 Direct:</b> {r2_link or 'N/A'}\n"
                            f"📝 <b>Subtitle:</b> {sub_link or 'None'}"
                        )
                        await bot.send_message(chat_id=int(Var.LOG_CHANNEL), text=log_text, disable_web_page_preview=True)
                    except Exception as e:
                        print(f"Log Error: {e}")

            elif drive_id:
                btn = InlineKeyboardButton(text=btn_text, url=f"https://drive.google.com/file/d/{drive_id}/view")
                if buttons and len(buttons[-1]) == 1: buttons[-1].append(btn)
                else: buttons.append([btn])

            try: await post_msg.edit_reply_markup(InlineKeyboardMarkup(buttons))
            except: pass
            await db.saveAnime(ani_id, ep_no, qual, msg.id)
            if ospath.exists(out_path): await aioremove(out_path)
            if sub_path and ospath.exists(sub_path): await aioremove(sub_path)

        ffLock.release()
        await stat_msg.delete()
        ani_cache.setdefault("completed", set()).add(ep_key)
        ani_cache["ongoing"].discard(ep_key)
        if ospath.exists(dl): await aioremove(dl)
    except Exception:
        await rep.report(format_exc(), "error")
        if ep_key: ani_cache["ongoing"].discard(ep_key)
        if ffLock.locked(): ffLock.release()

async def handle_start(client, message, payload: str):
    pass
