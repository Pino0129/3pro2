# ベースイメージ
FROM python:3.11-slim

# 必要パッケージ
RUN apt-get update && apt-get install -y wget unzip curl ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Flask アプリと ZIP をコピー
COPY . /app

# 依存関係
RUN pip install --no-cache-dir flask requests pydub

# VOICEVOX 展開
RUN unzip voicevox_engine-0.13.3.zip -d /opt/voicevox_engine \
    && chmod +x /opt/voicevox_engine/voicevox_engine-0.13.3/run || true

EXPOSE 8001 50021

# VOICEVOX + Flask を同時起動
CMD /opt/voicevox_engine/voicevox_engine-0.13.3/run --host 0.0.0.0 --port 50021 & python index.py
