# ベースイメージ
FROM python:3.11-slim

# 必要パッケージ
RUN apt-get update && apt-get install -y unzip ffmpeg && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# Flask アプリと zip ファイルをコピー
COPY . /app

# VOICEVOX Engine を zip から展開（ファイル名に合わせて修正）
RUN unzip voicevox_engine-0.13.3.zip -d /opt/voicevox_engine \
    && chmod +x /opt/voicevox_engine/run

# Python ライブラリ
RUN pip install --no-cache-dir flask requests pydub

# ポート
EXPOSE 8001 50021

# 起動コマンド
CMD ["sh", "-c", "/opt/voicevox_engine/run --host 0.0.0.0 & python app.py"]
