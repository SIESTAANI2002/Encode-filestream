import asyncio
import boto3
import math
import os
from time import time, sleep
from traceback import format_exc
from os import path as ospath
from urllib.parse import quote 

from pyrogram.errors import FloodWait
from bot import bot, Var
from .func_utils import editMessage, convertBytes
from .reporter import rep

try:
    from .gdrive_uploader import upload_to_drive
except ImportError:
    upload_to_drive = None

class TgUploader:
    def __init__(self, message):
        self.cancelled = False
        self.message = message
        self.__name = ""
        self.__qual = ""
        self.__client = bot
        self.__start = time()
        self.__updater = time()

    # ------------ R2 UPLOAD HELPER ------------
    def __upload_to_r2(self, file_path, content_type='video/mp4'):
        try:
            file_name = ospath.basename(file_path)
            file_size_mb = ospath.getsize(file_path) / (1024 * 1024)
            
            if content_type == 'text/vtt':
                folder_prefix = "subs/"
            elif file_size_mb > 450:
                folder_prefix = "large/"
            else:
                folder_prefix = "small/"

            r2_key = f"{folder_prefix}{file_name}"

            s3_client = boto3.client(
                's3',
                endpoint_url=Var.R2_ENDPOINT,
                aws_access_key_id=Var.R2_ACCESS_KEY,
                aws_secret_access_key=Var.R2_SECRET_KEY,
                config=boto3.session.Config(signature_version='s3v4')
            )
            
            s3_client.upload_file(
                file_path, 
                Var.R2_BUCKET, 
                r2_key, 
                ExtraArgs={'ContentType': content_type}
            )
            
            encoded_key = quote(r2_key)
            domain = Var.R2_DOMAIN.rstrip("/")
            return f"{domain}/{encoded_key}"
            
        except Exception as e:
            print(f"❌ R2 Upload Error: {e}")
            return None

    # ------------ TELEGRAM UPLOAD WORKER (BEAUTIFUL UI) ------------
    async def __upload_telegram(self, path, bin_channel):
        if not bin_channel:
            return None

        # 🔥 BEAUTIFUL PROGRESS FUNCTION
        async def progress(current, total):
            now = time()
            # 5 সেকেন্ড পর পর আপডেট হবে অথবা ১০০% হলে
            if (now - self.__updater) >= 5 or current == total:
                self.__updater = now
                
                # Calculation
                percentage = current * 100 / total
                speed = current / (now - self.__start) if (now - self.__start) > 0 else 0
                elapsed_time = round(now - self.__start)
                
                # ETA Calculation
                if speed > 0:
                    time_to_completion = round((total - current) / speed)
                else:
                    time_to_completion = 0
                
                # Time Formatting (MM:SS)
                def time_formatter(seconds):
                    m, s = divmod(seconds, 60)
                    h, m = divmod(m, 60)
                    return f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
                
                eta = time_formatter(time_to_completion)
                
                # Progress Bar Design (■■■□□□□□□□)
                filled_length = math.floor(percentage / 10)
                bar = "■" * filled_length + "□" * (10 - filled_length)
                
                # ✨ FINAL BEAUTIFUL TEXT
                text = (
                    f"<b>{self.__name}</b>\n\n"
                    f"⚡ <b>Parallel Uploading...</b>\n"
                    f"<code>[{bar}]</code> <b>{round(percentage, 1)}%</b>\n\n"
                    f"🚀 <b>Speed:</b> {convertBytes(speed)}/s\n"
                    f"📦 <b>Done:</b> {convertBytes(current)} / {convertBytes(total)}\n"
                    f"⏳ <b>ETA:</b> {eta}"
                )
                
                try:
                    await editMessage(self.message, text)
                except:
                    pass

        if Var.AS_DOC:
            return await self.__client.send_document(
                chat_id=bin_channel, document=path,
                thumb="thumb.jpg" if ospath.exists("thumb.jpg") else None,
                caption=f"<code>{self.__name}</code>", force_document=True,
                disable_notification=True, progress=progress
            )
        else:
            return await self.__client.send_video(
                chat_id=bin_channel, video=path,
                thumb="thumb.jpg" if ospath.exists("thumb.jpg") else None,
                caption=f"<code>{self.__name}</code>", supports_streaming=True,
                disable_notification=True, progress=progress
            )

    # ------------ DRIVE UPLOAD WORKER ------------
    async def __upload_gdrive(self, path):
        if upload_to_drive:
            try:
                # print(f"🚀 Starting Drive Upload: {self.__name}")
                drive_link = await upload_to_drive(path)
                if drive_link and "id=" in drive_link:
                    return drive_link.split("id=")[1]
            except Exception as e:
                print(f"⚠️ Drive Upload Error: {e}")
        return None

    # ------------ R2 UPLOAD WORKER ------------
    async def __upload_r2_worker(self, path, sub_path):
        r2_link = None
        sub_link = None
        
        if hasattr(Var, 'R2_ACCESS_KEY') and Var.R2_ACCESS_KEY:
            try:
                loop = asyncio.get_event_loop()
                # print(f"☁️ Starting R2 Upload: {self.__name}")
                
                r2_link = await loop.run_in_executor(None, self.__upload_to_r2, path, 'video/mp4')
                
                if sub_path and ospath.exists(sub_path):
                    sub_link = await loop.run_in_executor(None, self.__upload_to_r2, sub_path, 'text/vtt')
                    
            except Exception as e:
                print(f"⚠️ R2 Handler Error: {e}")
        
        return r2_link, sub_link

    # ------------ MAIN UPLOAD METHOD ------------
    async def upload(self, path, qual, sub_path=None):
        self.__name = ospath.basename(path)
        self.__qual = qual
        
        try:
            bin_channel = int(Var.FILE_STORE) if Var.FILE_STORE else None
            
            await editMessage(self.message, f"<b>{self.__name}</b>\n\n<i>⚡ Initializing Parallel Upload...</i>")

            # ✅ PARALLEL TASKS
            task_tg = asyncio.create_task(self.__upload_telegram(path, bin_channel))
            task_drive = asyncio.create_task(self.__upload_gdrive(path))
            task_r2 = asyncio.create_task(self.__upload_r2_worker(path, sub_path))

            # Wait for completion
            results = await asyncio.gather(task_tg, task_drive, task_r2)

            msg = results[0]
            drive_id = results[1]
            r2_data = results[2]
            
            r2_link = r2_data[0]
            sub_link = r2_data[1]

            return msg, drive_id, r2_link, sub_link

        except FloodWait as e:
            sleep(e.value * 1.5)
            return await self.upload(path, qual, sub_path)

        except Exception:
            await rep.report(format_exc(), "error")
            raise
