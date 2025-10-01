# ベースイメージ
FROM python:3.11-slim

# 必要パッケージ
RUN apt-get update && apt-get install -y wget unzip curl ffmpeg && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# Flask アプリをコピー
COPY . /app

# 依存関係
RUN pip install --no-cache-dir flask requests pydub

# VOICEVOX Engine ダウンロード（最新安定版URLに置き換える）
RUN wget --no-check-certificate https://github.com/VOICEVOX/voicevox_engine/releases/download/0.24.0/voicevox_engine_linux_x64.zip -O voicevox.zip \
    && unzip voicevox.zip -d /opt/voicevox_engine \
    && rm voicevox.zip \
    && chmod +x /opt/voicevox_engine/run

# ポート設定
EXPOSE 8001 50021

# VOICEVOX Engine と Flask を同時起動
CMD ["sh", "-c", "/opt/voicevox_engine/run --host 0.0.0.0 & python app.py"]
