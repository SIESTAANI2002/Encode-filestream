import os
import logging
from asyncio import create_task, create_subprocess_exec, all_tasks, sleep as asleep
from aiofiles import open as aiopen
from pyrogram import idle
from pyrogram.filters import command, user
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from os import path as ospath, execl, kill
from sys import executable
from signal import SIGKILL
import base64

# --- Aiohttp & Server Imports ---
from aiohttp import web
from bot.server.routes import routes, setup_cors # Ensure these exist in bot/server/routes.py

from bot import bot, Var, bot_loop, sch, LOGS, ffQueue, ffLock, ffpids_cache, ff_queued
from bot.core.auto_animes import fetch_animes, handle_start
from bot.core.func_utils import clean_up, new_task
from bot.modules.up_posts import upcoming_animes

# ----------------------
# /start command handler
# ----------------------
@bot.on_message(command("start"))
async def start(client, message):
    # Check for payload (Deep Linking)
    if len(message.command) > 1:
        start_payload = message.text.split(" ", 1)[1]
        # Payload processing for Stream/Download
        await handle_start(client, message, start_payload)
        return

    # Normal Start Message
    start_photo = getattr(Var, "START_PHOTO", None)
    start_msg = getattr(Var, "START_MSG", "Hello! Use the buttons to get your file.")
    start_buttons = getattr(Var, "START_BUTTONS", "")

    btns = []
    
    # --- Mini App Button ---
    mini_app_url = Var.MINI_APP_URL if hasattr(Var, 'MINI_APP_URL') else f"https://t.me/{Var.BOT_USERNAME}/app"
    btns.append([InlineKeyboardButton("📺 Open Mini App", web_app=WebAppInfo(url=mini_app_url))])

    buttons_list = start_buttons.split()
    first_row, second_row = [], []

    for i, b in enumerate(buttons_list):
        try:
            label, url = b.split("|")
            if i < 2:
                first_row.append(InlineKeyboardButton(label, url=url))
            else:
                second_row.append(InlineKeyboardButton(label, url=url))
        except:
            continue

    if first_row: btns.append(first_row)
    if second_row: btns.append(second_row)

    if start_photo:
        await client.send_photo(
            chat_id=message.chat.id,
            photo=start_photo,
            caption=start_msg.format(first_name=message.from_user.first_name),
            reply_markup=InlineKeyboardMarkup(btns)
        )
    else:
        await client.send_message(
            chat_id=message.chat.id,
            text=start_msg.format(first_name=message.from_user.first_name),
            reply_markup=InlineKeyboardMarkup(btns)
        )

# ----------------------
# Restart command
# ----------------------
@bot.on_message(command("restart") & user(Var.ADMINS))
@new_task
async def restart_cmd(client, message):
    rmessage = await message.reply('<i>Restarting...</i>')
    if sch.running:
        sch.shutdown(wait=False)
    await clean_up()
    if ffpids_cache:
        for pid in ffpids_cache:
            try:
                kill(pid, SIGKILL)
            except (OSError, ProcessLookupError):
                continue
    await (await create_subprocess_exec('python3', 'update.py')).wait()
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{rmessage.chat.id}\n{rmessage.id}\n")
    execl(executable, executable, "-m", "bot")

# ----------------------
# Post-restart handler
# ----------------------
async def restart():
    if ospath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="<i>Restarted!</i>")
        except Exception as e:
            LOGS.error(e)

# ----------------------
# FF queue loop
# ----------------------
async def queue_loop():
    LOGS.info("Queue Loop Started!")
    while True:
        if not ffQueue.empty():
            post_id = await ffQueue.get()
            await asleep(1.5)
            ff_queued[post_id].set()
            await asleep(1.5)
            async with ffLock:
                ffQueue.task_done()
        await asleep(10)

# ----------------------
# Web Server Setup (For Streaming)
# ----------------------
async def start_web_server():
    app = web.Application()
    app.add_routes(routes)
    
    # Enable CORS for External Mini App
    setup_cors(app)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    bind_address = "0.0.0.0"
    PORT = int(os.environ.get("PORT", 8080))
    
    site = web.TCPSite(runner, bind_address, PORT)
    await site.start()
    LOGS.info(f"Web Server Started at Port: {PORT}")

# ----------------------
# Main function
# ----------------------
async def main():
    sch.add_job(upcoming_animes, "cron", hour=0, minute=30)
    
    await bot.start()
    await restart()
    LOGS.info('Auto Anime Bot Started!')
    
    sch.start()
    bot_loop.create_task(queue_loop())
    
    # Start Streaming Server
    bot_loop.create_task(start_web_server())
    
    await fetch_animes()
    await idle()
    
    LOGS.info('Auto Anime Bot Stopped!')
    await bot.stop()
    for task in all_tasks():
        task.cancel()
    await clean_up()
    LOGS.info('Finished AutoCleanUp!')

if __name__ == '__main__':
    bot_loop.run_until_complete(main())
