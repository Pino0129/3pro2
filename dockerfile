# ベースイメージ
FROM python:3.11-slim

# 必要パッケージ
RUN apt-get update && apt-get install -y wget unzip curl ffmpeg && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# Flask アプリとZIPをコピー
COPY . /app
# ←もしZIPが含まれてないなら次を追加
# COPY voicevox_engine-0.13.3.zip /app

# 依存関係
RUN pip install --no-cache-dir flask requests pydub

# ✅ ZIP 展開
RUN unzip voicevox_engine-0.13.3.zip -d /opt/voicevox_engine \
    && ls -R /opt/voicevox_engine \
    && chmod +x /opt/voicevox_engine/voicevox_engine-0.13.3/run || true

# ポート
EXPOSE 8001 50021

# 起動
CMD ["sh", "-c", "/opt/voicevox_engine/voicevox_engine-0.13.3/run --host 0.0.0.0 & python app.py"]
