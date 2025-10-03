# ベースイメージ
FROM python:3.11-slim

# 必要パッケージ
RUN apt-get update && apt-get install -y wget unzip curl ffmpeg && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# Flask アプリと ZIP をコピー
COPY . /app

# 依存関係インストール
RUN pip install --no-cache-dir -r requirements.txt

# VOICEVOX エンジン展開＆実行権限付与
RUN unzip voicevox_engine-0.13.3.zip -d /opt/voicevox_engine \
    && chmod +x /opt/voicevox_engine/voicevox_engine-0.13.3/run

# ポート
EXPOSE 8001 50021

# 起動（VOICEVOX → Flask）
CMD sh -c "/opt/voicevox_engine/voicevox_engine-0.13.3/run --host 0.0.0.0 --port 50021 & python index.py"
