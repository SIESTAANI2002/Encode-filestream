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
        "type": "service_account",
        "project_id": "elegant-wavelet-410807",
        "private_key_id": "c7c9c8d92e9da3b61741ab0bbf0c2108a05b968f",
        "private_key": "-----BEGIN PRIVATE KEY-----\\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCsiEgLRuFjy3s/\\nwOjxyBAtxXk5QlKtMV/ogxN6BFvw7rSY/7xYFPxPHqdbQg5q3oUtUHEvefn5dNy8\\nNoCYSzFrPzzUL3Oo7RP6bRZgwACLKZIPgJC2l1oJSUWpKAYtXEUgUTlXQe95Wdo5\\nv4sI//za82R72Ksh28LAS1+oxjiCWzPnDqE5fg4HVMBWXFWQm5SjOcwRSaIU1Ena\\nHnYyPXwoYk5K4MirSaYGke6k82R7vH4mkzpyAR4/WyK3+LIxs2Pq5dMadk+t89z9\\ngy3yTg9YP2SHjXSCPp7tlJxEzjj6zmD6pCQxg5e2tLYv5lTX+t2RDQk9O6vsx/3v\\nQH00ApLpAgMBAAECggEAF1s7pYsq5/+b572Ny21yA0BAcOfxmVCd0zQrZtFAQRWP\\njUbRkHsGzQ8xSMFggkctcDz7lZnFpWeUmkYmkndbcVFWQsNJvQybL8Oky+QyLqSq\\nCT82WAGVRryMmaG5dFqRYRad1JoweRUY3ch4YfeFm35nk/x47lR5wN5zTL3I2JyW\\nmx9BmR5ZcrNbs54NQHxFYWddPDw3Zh2/OJnA/fiyJWjw2c7xP3tN6b2XZX23S0oY\\n9QOl5btBeawnBcqbvIId//7LNDOvxrWaBwYL44obBiOBiNroMbMXd6yZTug7c3Ge\\naAsM/yOsLuUa+AYXaDrfysItbH0ilmpK9Y5f5e8jIQKBgQDzuOYRiSGM4SH1jd54\\n5zDgkJyudl591mvrScT9noBHr535EvaGdC+4tJeJZSsdVLs51D8QmukilcUnbI4V\\neuUGvlJzM6TpZtf4GEWLZub2vxK8P3ptN7xYuh8cE+rT67BtB5SBUwFb+OjCSa8M\\n5p0PNbBNN38e9Al8Rh+A8Kkh9wKBgQC1OUzlx+iMqS0RN++j6u5XzerykLhAkdKh\\nyRuPcCQn1I02cAPLJeNLID8nEIsyzz8CU8/PFLG+lC+zN4RsCFqkNiHwyCYAo8A6\\n3WPev2Y21MXxj/fCXkQlHH0XDukZAdAbX/mPpXjnaUXIH27t9tc5/vhQfXfJlGtd\\nbGE7Y3a6HwKBgQDx7RIDShoRm9B3zRGO9f6giyvcSgdV5ihN8HYoQtOXVQ38lgQ8\\nRsywDiN18QSxItCOgM7xDrRo7j47+he33rvEy9tQG22RedLbpEw0KjsNp3FTh7dg\\n/rhpYqdK2cJ6BjSkpaeWD+0DfLqfUUEAD1LMLEELBRGciiV4RKs09K8O1QKBgQCi\\ng68tBJfLxE6w+TuDAMQao4PFYPiKlvqPsTxw5jzWJys3nT4ZqHFrRpC7pH9f4jB8\\nEtLxvnojENqx2eB7zQYT6qOHPMWvnylc4HqWH4g3NZoJJXUmrchoi2K2Ed4BWfnZ\\nArlXEyoYQ/SbIW0mI00hKkBeVhXdBKc/kViknG61OwKBgAFLZiRFQLpl39AAccDc\\nZnW/r9hPQSLF/AbvLT44MdhDd/Le69pvAWb8ZhMaos3XBQUUgivUYWEg6vCWJAmp\\nLkuiLkXCXkDuzT+uczUKRq26H1oXMJGfgkSOI4dwndrtuNE++hsrdKGz9DUs8RkQ\\nu8nIiPLB7CNIwsfdpCJ4UR5T\\n-----END PRIVATE KEY-----\\n",
        "client_email": "mfc--btd6m2b8qj9l3w63izvt3y04e@elegant-wavelet-410807.iam.gserviceaccount.com",
        "client_id": "103084241973221581645",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/mfc--btd6m2b8qj9l3w63izvt3y04e@elegant-wavelet-410807.iam.gserviceaccount.com",
        "universe_domain": "googleapis.com"
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
