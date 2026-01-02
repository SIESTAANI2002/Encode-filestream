from os import path as opath, getenv
from logging import FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info
from subprocess import run as srun
from dotenv import load_dotenv

if opath.exists("log.txt"):
    with open("log.txt", 'r+') as f:
        f.truncate(0)

basicConfig(format="[%(asctime)s] [%(name)s | %(levelname)s] - %(message)s [%(filename)s:%(lineno)d]",
            datefmt="%m/%d/%Y, %H:%M:%S %p",
            handlers=[FileHandler('log.txt'), StreamHandler()],
            level=INFO)

load_dotenv('config.env', override=True)

# 🛠️ FIX: যদি ব্রাঞ্চ নাম না থাকে, তবে ডিফল্ট হিসেবে 'main' ব্যবহার করবে
UPSTREAM_REPO = getenv('UPSTREAM_REPO')
UPSTREAM_BRANCH = getenv('UPSTREAM_BRANCH', 'main')

if UPSTREAM_REPO:
    if opath.exists('.git'):
        srun(["rm", "-rf", ".git"])
    
    # লগিং করা হচ্ছে যে আপডেট শুরু হয়েছে
    log_info(f"Updating from {UPSTREAM_REPO} (Branch: {UPSTREAM_BRANCH})...")

    cmd = f"""
    git init -q \
    && git config --global user.email "your_email@gmail.com" \
    && git config --global user.name "BotUpdater" \
    && git add . \
    && git commit -sm update -q \
    && git remote add origin {UPSTREAM_REPO} \
    && git fetch origin -q \
    && git reset --hard origin/{UPSTREAM_BRANCH} -q
    """

    update = srun(cmd, shell=True)

    if update.returncode == 0:
        log_info('✅ Successfully updated with latest commit from UPSTREAM_REPO')
    else:
        # ⚠️ এখানে বিস্তারিত এরর দেখার ব্যবস্থা থাকলে ভালো হতো, তবে আপাতত এরর মেসেজ
        log_error('❌ Something went wrong while updating! Check UPSTREAM_REPO and BRANCH url.')
else:
    log_error("UPSTREAM_REPO variable is missing! Skipping update.")
