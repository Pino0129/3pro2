# ベースイメージ
FROM python:3.11-slim

# 必要パッケージ（unzip が必須！）
RUN apt-get update && apt-get install -y wget unzip curl ffmpeg && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# Flask アプリをコピー
COPY . /app

# 依存関係
RUN pip install --no-cache-dir flask requests pydub

# ZIP を解凍（ファイル名はあなたのものに合わせる）
RUN unzip voicevox_engine-0.13.3.zip -d /opt/voicevox_engine \
    && chmod +x /opt/voicevox_engine/run

# ポート公開
EXPOSE 8001 50021

# VOICEVOX Engine と Flask を同時起動
CMD ["sh", "-c", "/opt/voicevox_engine/run --host 0.0.0.0 & python app.py"]
