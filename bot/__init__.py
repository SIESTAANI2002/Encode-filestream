# ===================== ASYNCIO FIX =====================
import asyncio
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# ===================== STANDARD IMPORTS =====================
import json
import os
import subprocess
import shutil
from os import path as ospath, mkdir, system, getenv
from logging import INFO, ERROR, FileHandler, StreamHandler, basicConfig, getLogger
from asyncio import Queue, Lock
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# ===================== LOGGING =====================
basicConfig(
    format="[%(asctime)s] [%(name)s | %(levelname)s] - %(message)s [%(filename)s:%(lineno)d]",
    datefmt="%m/%d/%Y, %H:%M:%S %p",
    handlers=[FileHandler('log.txt'), StreamHandler()],
    level=INFO
)
getLogger("pyrogram").setLevel(ERROR)
LOGS = getLogger(__name__)

# ===================== LOAD ENV =====================
load_dotenv("config.env")

# ===================== GLOBAL CACHES =====================
ani_cache = {
    "fetch_animes": True,
    "ongoing": set(),
    "completed": set()
}
ffpids_cache = list()
ffLock = Lock()
ffQueue = Queue()
ff_queued = dict()

# ===================== CONFIG VARS =====================
class Var:
    API_ID = getenv("API_ID")
    API_HASH = getenv("API_HASH")
    BOT_TOKEN = getenv("BOT_TOKEN")
    MONGO_URI = getenv("MONGO_URI")
    
    if not BOT_TOKEN or not API_HASH or not API_ID or not MONGO_URI:
        LOGS.critical('Important Variables Missing. Fill Up and Retry..!! Exiting Now...')
        exit(1)
                
    try:
        API_ID = int(API_ID)
        OWNER_ID = int(getenv("OWNER_ID", "123456789"))
        MAIN_CHANNEL = int(getenv("MAIN_CHANNEL", "0"))
        LOG_CHANNEL = int(getenv("LOG_CHANNEL", "0"))
        FILE_STORE = int(getenv("FILE_STORE", "0"))
        ADMINS = list(map(int, getenv("ADMINS", "1242011540").split()))
    except ValueError:
        LOGS.error("One of the ID variables (API_ID, CHANNELS, ADMINS) is not an integer!")
        exit(1)

    HEROKU_APP_URL = getenv("HEROKU_APP_URL", "")
    URL = getenv("URL", "") or HEROKU_APP_URL
    MINI_APP_URL = getenv("MINI_APP_URL", "")
    PORT = getenv("PORT", "8080")
    
    RSS_ITEMS = getenv("RSS_ITEMS", "").split()
    RSS_TOR = getenv("RSS_TOR", "").split()
    try:
        FSUB_CHATS = list(map(int, getenv('FSUB_CHATS', '').split()))
    except:
        FSUB_CHATS = []
    BACKUP_CHANNEL = getenv("BACKUP_CHANNEL") or ""
    
    TOKYO_API_KEY = getenv("TOKYO_API_KEY", "")
    TOKYO_USER = getenv("TOKYO_USER", "")
    TOKYO_PASS = getenv("TOKYO_PASS", "")
    WEBSITE = getenv("WEBSITE", "")
    TG_PROTECT_CONTENT = getenv("TG_PROTECT_CONTENT", "")
    BOT_USERNAME = getenv("BOT_USERNAME", "") 

    R2_BUCKET = getenv("R2_BUCKET", "")
    R2_ENDPOINT = getenv("R2_ENDPOINT", "")
    R2_ACCESS_KEY = getenv("R2_ACCESS_KEY", "")
    R2_SECRET_KEY = getenv("R2_SECRET_KEY", "")
    R2_DOMAIN = getenv("R2_DOMAIN", "")
    
    SERVICE_ACCOUNT_JSON = {
        
    }
    _sa_json_str = getenv("SERVICE_ACCOUNT_JSON")
    if _sa_json_str:
        try:
            SERVICE_ACCOUNT_JSON = json.loads(_sa_json_str)
        except:
            LOGS.warning("Invalid Service Account JSON provided!")

    SEND_SCHEDULE = getenv("SEND_SCHEDULE", "False").lower() == "true"
    BRAND_UNAME = getenv("BRAND_UNAME", "@username")
    SECOND_BRAND = getenv("SECOND_BRAND", "AnimeToki")
    
    FFCODE_1080 = getenv("FFCODE_1080") or """ffmpeg -i '{}' -progress '{}' -preset veryfast -c:v libx264 -s 1920x1080 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y"""
    FFCODE_720 = getenv("FFCODE_720") or """ffmpeg -i '{}' -progress '{}' -preset superfast -c:v libx264 -s 1280x720 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y"""
    FFCODE_480 = getenv("FFCODE_480") or """ffmpeg -i '{}' -progress '{}' -preset superfast -c:v libx264 -s 854x480 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y"""
    FFCODE_360 = getenv("FFCODE_360") or """ffmpeg -i '{}' -progress '{}' -preset superfast -c:v libx264 -s 640x360 -pix_fmt yuv420p -crf 30 -c:a libopus -b:a 32k -c:s copy -map 0 -ac 2 -ab 32k -vbr 2 -level 3.1 '{}' -y"""
    QUALS = getenv("QUALS", "720 1080").split()
        
    QUALS = getenv("QUALS", "720 1080").split()

    DRIVE_FOLDER_ID = getenv("DRIVE_FOLDER_ID", "")
    AS_DOC = getenv("AS_DOC", "True").lower() == "true"
    THUMB = getenv("THUMB", "https://te.legra.ph/file/621c8d40f9788a1db7753.jpg")
    AUTO_DEL = getenv("AUTO_DEL", "True").lower() == "true"
    DEL_TIMER = int(getenv("DEL_TIMER", "600"))
    START_PHOTO = getenv("START_PHOTO", "https://te.legra.ph/file/120de4dbad87fb20ab862.jpg")
    START_MSG = getenv("START_MSG", "<b>Hey {first_name}</b>,\n\n    <i>I am Auto Animes Store & Automater Encoder Build with ❤️ !!</i>")
    START_BUTTONS = getenv("START_BUTTONS", "UPDATES|https://telegram.me/Matiz_Tech SUPPORT|https://t.me/+p78fp4UzfNwzYzQ5")

# ===================== INIT FILES & DIRS =====================
if Var.THUMB and not ospath.exists("thumb.jpg"):
    system(f"wget -q {Var.THUMB} -O thumb.jpg")
    LOGS.info("Thumbnail downloaded")

for folder in ("encode", "thumbs", "downloads"):
    if not ospath.isdir(folder):
        mkdir(folder)

# ===================== BOT INIT (Network Fixes) =====================
try:
    bot = Client(
        name="AutoAniAdvance",
        api_id=Var.API_ID,
        api_hash=Var.API_HASH,
        bot_token=Var.BOT_TOKEN,
        plugins=dict(root="bot/modules"),
        parse_mode=ParseMode.HTML,
        in_memory=True,
        ipv6=False,                 # ✅ FIX: Disable IPv6 for Heroku Stability
        max_concurrent_transmissions=2  # ✅ FIX: Lower concurrency to prevent Offset Error
    )

    bot_loop = bot.loop
    sch = AsyncIOScheduler(timezone="Asia/Kolkata", event_loop=bot_loop)

except Exception as e:
    LOGS.error(str(e))
    exit(1)
