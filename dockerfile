# ベースイメージ
FROM python:3.11-slim

# 必要パッケージ
RUN apt-get update && \
    apt-get install -y wget unzip curl ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# アプリをコピー
COPY . /app

# Python 依存関係
RUN pip install --no-cache-dir flask requests pydub

# プロジェクト内の zip を /opt/voicevox_engine に解凍
COPY voicevox_engine_linux.zip /opt/voicevox_engine.zip
RUN unzip /opt/voicevox_engine.zip -d /opt/voicevox_engine \
    && rm /opt/voicevox_engine.zip \
    && chmod +x /opt/voicevox_engine/run

# 起動スクリプトをコピー
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Render は PORT 環境変数を使う
EXPOSE 50021 8000

# 起動
ENTRYPOINT ["/app/entrypoint.sh"]
