FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# সিস্টেম ডিপেন্ডেন্সি ইন্সটল
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y \
    software-properties-common \
    tzdata \
    curl \
    git \
    wget \
    jq \
    pv \
    ffmpeg \
    mediainfo \
    gcc \
    g++ \
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3-libtorrent \
    libtorrent-rasterbar-dev \
    libsm6 \
    libxext6 \
    libfontconfig1 \
    libxrender1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# পাইথন এবং পিপ সিম্বলিক লিংক
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# ওয়ার্কিং ডিরেক্টরি সেট করা
WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

# সব ফাইল কপি করা
COPY . .

# 🛠️ FIX: Libtorrent এর ইনভ্যালিড মেটাডেটা রিমুভ করা (এটা ছাড়া বিল্ড ফেইল করবে)
RUN rm -rf /usr/lib/python3/dist-packages/libtorrent*.egg-info

# পিপ আপগ্রেড
RUN pip install --upgrade pip setuptools wheel

# 🔥 Blinker ফিক্স এবং Requirements ইন্সটল
RUN pip install --no-cache-dir --ignore-installed blinker && \
    pip install --no-cache-dir -r requirements.txt

# torrentp আলাদাভাবে ইন্সটল
RUN pip install --no-cache-dir torrentp==0.1.7 --no-deps

# run.sh কে এক্সিকিউট পারমিশন দেওয়া (খুবই জরুরি)
RUN chmod +x run.sh

# Heroku পোর্ট এক্সপোজ
EXPOSE 8080

# ✅ CMD পরিবর্তন: এখন run.sh রান হবে (update.py + bot)
CMD ["bash", "run.sh"]
