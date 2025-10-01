#!/bin/sh

# VOICEVOX Engine をバックグラウンドで起動
/opt/voicevox_engine/run --host 0.0.0.0 --port 50021 &

# Flask を前景で起動
# Render は環境変数 PORT を自動設定
export FLASK_APP=app.py
export FLASK_RUN_HOST=0.0.0.0
export FLASK_RUN_PORT=${PORT:-8000}

flask run
