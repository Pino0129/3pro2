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

# ✅ ZIP を展開（フォルダ内に run がある構造に対応）
RUN unzip voicevox_engine-0.13.3.zip -d /opt/voicevox_engine \
    && chmod +x /opt/voicevox_engine/voicevox_engine-0.13.3/run

# ポート設定
EXPOSE 8001 50021

# 起動コマンド
CMD ["sh", "-c", "/opt/voicevox_engine/voicevox_engine-0.13.3/run --host 0.0.0.0 & python app.py"]
