# 音声合成アプリ

COEIROINKを使用した音声合成Webアプリケーションです。

## 機能

- テキストファイルから会話データを読み込み
- 複数のスピーカーによる音声合成
- Webインターフェースでの操作

## 必要な環境

- Python 3.7+
- COEIROINKサーバー（ポート50032で起動）

## セットアップ

1. 依存関係のインストール:
   ```bash
   pip install -r requirements.txt
   ```

2. COEIROINKサーバーの起動:
   - COEIROINKをインストールし、ポート50032で起動

3. アプリケーションの起動:
   ```bash
   python index.py
   ```

## 使用方法

1. 同じディレクトリに `text.txt` ファイルを配置
2. ブラウザで `http://localhost:8001` にアクセス
3. 「音声を合成」ボタンをクリック

## 環境変数

- `COEIROINK_BASE_URL`: COEIROINKサーバーのURL（デフォルト: http://localhost:50032）
- `COEIROINK_TIMEOUT`: タイムアウト時間（デフォルト: 30秒）
- `AUDIO_OUTPUT_DIR`: 音声ファイルの出力ディレクトリ
- `SECRET_KEY`: Flaskのシークレットキー
