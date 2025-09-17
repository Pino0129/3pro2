import json
import requests
import subprocess
import os
import time
from pathlib import Path
from datetime import datetime
import wave
import contextlib
from flask import Flask, render_template, request, send_file, url_for, flash
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# COEIROINKサーバーの設定
COEIROINK_BASE_URL = os.environ.get('COEIROINK_BASE_URL', 'http://localhost:50032')
COEIROINK_TIMEOUT = int(os.environ.get('COEIROINK_TIMEOUT', '30'))

# スピーカーIDの定義
VOICE_ID_man = 0
VOICE_ID_TSUKUYOMI = 1

def clean_text(text):
    """テキストをクリーニングする"""
    # 「セリフ:」などのプレフィックスを削除
    text = re.sub(r'^セリフ:\s*', '', text)
    # 余分な空白を削除
    text = text.strip()
    return text

def download_and_setup_coeiroink():
    """COEIROINKをダウンロードしてセットアップする"""
    coeiroink_dir = "COEIROINK-linux-x64"
    coeiroink_executable = os.path.join(coeiroink_dir, "COEIROINK")
    
    # 既にCOEIROINKが存在する場合はスキップ
    if os.path.exists(coeiroink_executable):
        print("COEIROINKは既に存在します")
        return True
    
    try:
        print("COEIROINKをダウンロード中...")
        
        # Linux版COEIROINKをダウンロード
        download_url = "https://github.com/COEIROINK/COEIROINK/releases/latest/download/COEIROINK-linux-x64.zip"
        
        # curlでダウンロード（wgetの代替）
        result = subprocess.run([
            "curl", "-L", "-o", "COEIROINK-linux-x64.zip", download_url
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"curlでのダウンロードに失敗しました: {result.stderr}")
            # wgetを試行
            result = subprocess.run([
                "wget", "-O", "COEIROINK-linux-x64.zip", download_url
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                print(f"wgetでのダウンロードも失敗しました: {result.stderr}")
                return False
        
        print("COEIROINKの解凍中...")
        
        # unzipで解凍
        result = subprocess.run([
            "unzip", "-o", "COEIROINK-linux-x64.zip"
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"解凍に失敗しました: {result.stderr}")
            return False
        
        # 実行権限を付与
        if os.path.exists(coeiroink_executable):
            os.chmod(coeiroink_executable, 0o755)
            print("COEIROINKのセットアップが完了しました")
            
            # ダウンロードファイルを削除
            if os.path.exists("COEIROINK-linux-x64.zip"):
                os.remove("COEIROINK-linux-x64.zip")
            
            return True
        else:
            print("COEIROINKの実行ファイルが見つかりません")
            return False
            
    except subprocess.TimeoutExpired:
        print("COEIROINKのダウンロードがタイムアウトしました")
        return False
    except Exception as e:
        print(f"COEIROINKのセットアップ中にエラーが発生しました: {str(e)}")
        return False

def start_coeiroink_server():
    """COEIROINKサーバーを起動する"""
    coeiroink_executable = os.path.join("COEIROINK-linux-x64", "COEIROINK")
    
    print(f"COEIROINK実行ファイルのパス: {coeiroink_executable}")
    print(f"ファイルの存在確認: {os.path.exists(coeiroink_executable)}")
    
    if not os.path.exists(coeiroink_executable):
        print("COEIROINKが見つかりません。ダウンロードを試行します...")
        if not download_and_setup_coeiroink():
            print("COEIROINKのセットアップに失敗しました")
            return None
    
    try:
        print("COEIROINKサーバーを起動中...")
        
        # COEIROINKサーバーをバックグラウンドで起動
        process = subprocess.Popen([
            coeiroink_executable,
            "--host", "0.0.0.0",
            "--port", "50032"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # サーバーの起動を待つ
        time.sleep(5)
        
        # プロセスの状態を確認
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"COEIROINKプロセスが終了しました。終了コード: {process.returncode}")
            print(f"標準出力: {stdout.decode()}")
            print(f"エラー出力: {stderr.decode()}")
            return None
        
        # サーバーが起動しているかチェック
        if check_coeiroink_server():
            print("COEIROINKサーバーが正常に起動しました")
            return process
        else:
            print("COEIROINKサーバーの起動に失敗しました")
            process.terminate()
            return None
            
    except Exception as e:
        print(f"COEIROINKサーバーの起動中にエラーが発生しました: {str(e)}")
        return None

def synthesize_with_google_tts(text, voice_name="ja-JP-Wavenet-A"):
    """Google Cloud Text-to-Speechを使用して音声合成"""
    try:
        from google.cloud import texttospeech
        
        # クライアントを初期化
        client = texttospeech.TextToSpeechClient()
        
        # 音声合成の設定
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="ja-JP",
            name=voice_name
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        
        # 音声合成を実行
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # 一時ファイルに保存
        temp_file = f"temp_google_{len(text)}.wav"
        with open(temp_file, "wb") as out:
            out.write(response.audio_content)
        
        return temp_file
        
    except ImportError:
        print("Google Cloud Text-to-Speechライブラリがインストールされていません")
        return None
    except Exception as e:
        print(f"Google TTSでの音声合成に失敗しました: {str(e)}")
        return None

def get_speakers():
    """利用可能なスピーカー情報を取得する"""
    try:
        response = requests.get(f"{COEIROINK_BASE_URL}/v1/speakers", timeout=10)
        if response.status_code == 200:
            speakers = response.json()
            
            # スピーカー情報を整理
            for speaker in speakers:
                # スピーカー名の設定
                speaker_uuid = speaker.get("speakerUuid", "")
                if speaker_uuid == "d312d0fb-d38d-434e-825d-cbcbfd105ad0":
                    speaker["name"] = "男性"
                elif speaker_uuid == "3c37646f-3881-5374-2a83-149267990abc":
                    speaker["name"] = "女性"
                else:
                    speaker["name"] = f"スピーカー_{speaker_uuid[:8]}"
                
                # スタイル情報の検証と修正
                styles = speaker.get("styles", [])
                if not styles:
                    print(f"警告: スピーカー {speaker['name']} にスタイルが設定されていません")
                    speaker["styles"] = [{"styleId": 0, "styleName": "デフォルト"}]
                else:
                    # スタイルIDを数値に変換
                    for style in styles:
                        if isinstance(style.get("styleId"), str):
                            try:
                                style["styleId"] = int(style["styleId"])
                            except ValueError:
                                print(f"警告: スピーカー {speaker['name']} のスタイルIDが無効です: {style.get('styleId')}")
                                style["styleId"] = 0
            
            # スピーカー情報の表示
            print("\n=== 利用可能なスピーカー情報 ===")
            for speaker in speakers:
                print(f"\nスピーカー: {speaker['name']}")
                print(f"UUID: {speaker['speakerUuid']}")
                print("スタイル:")
                for style in speaker.get("styles", []):
                    print(f"  - {style.get('styleName', '不明')} (ID: {style.get('styleId', 0)})")
            print("\n=============================")
            
            return speakers
        else:
            print(f"スピーカー情報の取得に失敗しました: {response.status_code}")
            print(f"応答: {response.text}")
            return None
    except Exception as e:
        print(f"サーバーへの接続に失敗しました: {e}")
        return None

# COEIROINKサーバーを起動
coeiroink_process = start_coeiroink_server()

# グローバル変数としてスピーカー情報を保持
speakers = get_speakers()
if not speakers:
    print("Warning: Failed to get speaker information. App will run without voice synthesis.")
    speakers = []  # 空のリストで初期化
    print("COEIROINKが利用できないため、音声合成機能は無効です。")
    print("代替手段として、Google Cloud Text-to-Speechの使用を検討してください。")

def get_text_file_path():
    """同じ階層のtext.txtファイルのパスを取得する"""
    return os.path.join(os.path.dirname(__file__), "text.txt")

def get_desktop_path():
    """デスクトップのパスを取得する"""
    return str(Path.home() / "Desktop")

def generate_filename():
    """ファイル名を生成する"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"voice_dialogue_{timestamp}.wav"

def combine_wav_files(wav_files, output_path):
    """複数のWAVファイルを結合する"""
    with wave.open(wav_files[0], 'rb') as first_file:
        params = first_file.getparams()
        n_channels = first_file.getnchannels()
        sample_width = first_file.getsampwidth()
        frame_rate = first_file.getframerate()

    with wave.open(output_path, 'wb') as output_file:
        output_file.setparams(params)
        
        for wav_file in wav_files:
            with wave.open(wav_file, 'rb') as input_file:
                output_file.writeframes(input_file.readframes(input_file.getnframes()))
                if wav_file != wav_files[-1]:
                    silence_duration = 0.5
                    silence_frames = int(silence_duration * frame_rate)
                    silence_data = b'\x00' * (silence_frames * n_channels * sample_width)
                    output_file.writeframes(silence_data)

def get_output_directory():
    """音声ファイルの出力ディレクトリを取得する"""
    # 環境変数で出力ディレクトリを指定可能
    output_dir = os.environ.get('AUDIO_OUTPUT_DIR', os.path.join(os.path.dirname(__file__), 'audio_output'))
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def check_coeiroink_server():
    """COEIROINKサーバーの状態を確認する"""
    try:
        response = requests.get(f"{COEIROINK_BASE_URL}/v1/speakers", timeout=5)
        if response.status_code == 200:
            speakers = response.json()
            print(f"COEIROINKサーバーに接続できました。利用可能なスピーカー数: {len(speakers)}")
            return True
        else:
            print(f"COEIROINKサーバーに接続できません。ステータスコード: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"COEIROINKサーバーに接続できません: {str(e)}")
        return False

def validate_synthesis_params(speaker, params):
    """合成パラメータの検証を行う"""
    errors = []
    
    # テキストの検証
    if not params["text"] or len(params["text"].strip()) == 0:
        errors.append("テキストが空です")
    
    # スピーカーUUIDの検証
    if not speaker.get("speakerUuid"):
        errors.append("スピーカーUUIDが無効です")
    
    # スタイルIDの検証
    styles = speaker.get("styles", [])
    if not styles:
        errors.append("スピーカーのスタイルが設定されていません")
    else:
        valid_style_ids = [style.get("styleId", 0) for style in styles]
        if params["styleId"] not in valid_style_ids:
            errors.append(f"無効なスタイルIDです: {params['styleId']} (有効な値: {valid_style_ids})")
            # デフォルトのスタイルIDを使用
            params["styleId"] = valid_style_ids[0]
            print(f"警告: スタイルIDを {params['styleId']} に変更しました")
    
    # 速度とピッチの範囲チェック
    if not 0.5 <= params["speedScale"] <= 2.0:
        errors.append(f"速度の値が範囲外です: {params['speedScale']} (0.5-2.0の範囲で指定してください)")
        params["speedScale"] = max(0.5, min(2.0, params["speedScale"]))
        print(f"警告: 速度を {params['speedScale']} に調整しました")
    
    if not -0.5 <= params["pitchScale"] <= 0.5:
        errors.append(f"ピッチの値が範囲外です: {params['pitchScale']} (-0.5-0.5の範囲で指定してください)")
        params["pitchScale"] = max(-0.5, min(0.5, params["pitchScale"]))
        print(f"警告: ピッチを {params['pitchScale']} に調整しました")
    
    return errors

def synthesize_dialogue(lines, speakers):
    """会話を合成する"""
    if not check_coeiroink_server():
        return None, "COEIROINKサーバーに接続できません。サーバーが起動しているか確認してください。"

    if not speakers:
        return None, "利用可能なスピーカー情報がありません"

    temp_files = []
    try:
        for line in lines:
            speaker_id = line["id"]
            if speaker_id >= len(speakers):
                print(f"無効なスピーカーIDです: {speaker_id} (利用可能なスピーカー数: {len(speakers)})")
                continue

            speaker = speakers[speaker_id]
            speaker_name = speaker.get("name", "不明")
            print(f"\nスピーカー {speaker_id} ({speaker_name}) の処理を開始")
            
            # テキストのクリーニング
            cleaned_text = clean_text(line["text"])
            
            # スタイル情報の取得
            styles = speaker.get("styles", [])
            if not styles:
                print(f"警告: スピーカー {speaker_name} にスタイルが設定されていません")
                style_id = 0
                style_name = "デフォルト"
            else:
                # 最初のスタイルを使用
                style = styles[0]
                style_id = style.get("styleId", 0)
                style_name = style.get("styleName", "デフォルト")
            
            synthesis_params = {
                "text": cleaned_text,
                "speakerUuid": speaker["speakerUuid"],
                "styleId": style_id,
                "speedScale": line["speed"],
                "pitchScale": line["pitch"],
                "intonationScale": 1.0,
                "volumeScale": 1.0,
                "prePhonemeLength": 0.0,
                "postPhonemeLength": 0.0,
                "outputSamplingRate": 44100,
            }

            # パラメータの検証
            validation_errors = validate_synthesis_params(speaker, synthesis_params)
            if validation_errors:
                error_msg = "合成パラメータの検証に失敗しました:\n" + "\n".join(f"- {err}" for err in validation_errors)
                print(error_msg)
                if not validation_errors:  # 警告のみの場合は続行
                    print("警告は無視して処理を続行します")
                else:
                    continue

            print("合成リクエストの詳細:")
            print(f"- テキスト: '{cleaned_text}'")
            print(f"- スピーカー: {speaker_name} (UUID: {speaker['speakerUuid']})")
            print(f"- スタイル: {style_name} (ID: {style_id})")
            print(f"- 速度: {synthesis_params['speedScale']}")
            print(f"- ピッチ: {synthesis_params['pitchScale']}")

            try:
                response = requests.post(
                    f"{COEIROINK_BASE_URL}/v1/synthesis",
                    json=synthesis_params,
                    headers={"Content-Type": "application/json", "Accept": "audio/wav"},
                    timeout=COEIROINK_TIMEOUT
                )

                print(f"サーバー応答ステータス: {response.status_code}")
                if response.status_code != 200:
                    error_detail = response.text
                    print(f"合成に失敗しました (ステータス {response.status_code})")
                    print(f"エラー詳細: {error_detail}")
                    print(f"リクエストパラメータ: {json.dumps(synthesis_params, ensure_ascii=False, indent=2)}")
                    continue

                temp_file = f"temp_{len(temp_files)}.wav"
                with open(temp_file, "wb") as f:
                    f.write(response.content)
                temp_files.append(temp_file)
                print(f"音声ファイルの作成に成功: {temp_file}")

            except requests.exceptions.RequestException as e:
                print(f"リクエストに失敗しました: {str(e)}")
                print(f"リクエストパラメータ: {json.dumps(synthesis_params, ensure_ascii=False, indent=2)}")
                continue

        if not temp_files:
            return None, "音声ファイルが正常に生成されませんでした"

        output_dir = get_output_directory()
        output_filename = generate_filename()
        output_path = os.path.join(output_dir, output_filename)
        
        print(f"{len(temp_files)}個の音声ファイルを結合中: {output_path}")
        combine_wav_files(temp_files, output_path)
        return output_path, None

    except Exception as e:
        print(f"synthesize_dialogueで予期せぬエラーが発生しました: {str(e)}")
        import traceback
        print(f"エラーの詳細:\n{traceback.format_exc()}")
        return None, f"予期せぬエラーが発生しました: {str(e)}"

    finally:
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    print(f"一時ファイルを削除しました: {temp_file}")
                except Exception as e:
                    print(f"一時ファイルの削除に失敗しました {temp_file}: {str(e)}")

def parse_text_content(text_content):
    """テキストファイルの内容を解析して音声合成用のデータに変換する"""
    lines = []
    current_speaker = None
    current_text = []
    current_speed = 1.0
    current_pitch = 0.0
    
    print("=== テキストファイルの内容 ===")
    for line in text_content.split('\n'):
        text = line.strip()
        print(f"行: '{text}'")  # デバッグ出力
        if not text:
            continue
            
        # 話者の設定を検出
        speaker_match = re.match(r'\[(男性|女性)\]', text)
        if speaker_match:
            print(f"話者を検出: {speaker_match.group(1)}")  # デバッグ出力
            # 前の話者のデータを保存
            if current_speaker is not None and current_text:
                speaker_id = VOICE_ID_man if current_speaker == "男性" else VOICE_ID_TSUKUYOMI
                lines.append({
                    "text": " ".join(current_text),
                    "id": speaker_id,
                    "pitch": current_pitch,
                    "speed": current_speed
                })
                current_text = []
            
            current_speaker = speaker_match.group(1)
            current_speed = 1.0  # デフォルト値
            current_pitch = 0.0  # デフォルト値
            continue
            
        # 速度の設定を検出
        speed_match = re.match(r'速度:\s*([\d.]+)', text)
        if speed_match:
            current_speed = float(speed_match.group(1))
            print(f"速度を設定: {current_speed}")  # デバッグ出力
            continue
            
        # ピッチの設定を検出
        pitch_match = re.match(r'ピッチ:\s*([-\d.]+)', text)
        if pitch_match:
            current_pitch = float(pitch_match.group(1))
            print(f"ピッチを設定: {current_pitch}")  # デバッグ出力
            continue
            
        # 通常のテキスト
        if current_speaker is not None:
            current_text.append(text)
            print(f"テキストを追加: {text}")  # デバッグ出力
    
    # 最後の話者のデータを保存
    if current_speaker is not None and current_text:
        speaker_id = VOICE_ID_man if current_speaker == "男性" else VOICE_ID_TSUKUYOMI
        lines.append({
            "text": " ".join(current_text),
            "id": speaker_id,
            "pitch": current_pitch,
            "speed": current_speed
        })
    
    print(f"=== 解析結果: {len(lines)}行のデータ ===")  # デバッグ出力
    for line in lines:
        print(f"行: {line}")  # デバッグ出力
    
    return lines

@app.route("/")
def index():
    """メインページを表示"""
    try:
        # 同じ階層のtext.txtを読み込む
        file_path = get_text_file_path()
        
        if not os.path.exists(file_path):
            return render_template("index.html", error="同じ階層にtext.txtが見つかりません")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        lines = parse_text_content(text_content)
        
        if not lines:
            return render_template("index.html", error="有効な会話データが見つかりませんでした")
            
        return render_template("index.html", lines=lines)
    except Exception as e:
        return render_template("index.html", error=f"ファイルの処理中にエラーが発生しました: {str(e)}")

@app.route("/synthesize", methods=["POST"])
def synthesize():
    """音声合成を実行"""
    try:
        print("=== 音声合成リクエスト開始 ===")
        
        # COEIROINKサーバーの状態を確認
        if not check_coeiroink_server():
            error_msg = "COEIROINKサーバーに接続できません。サーバーが起動していないか、ダウンロードに失敗している可能性があります。"
            print(error_msg)
            return {"error": error_msg}, 400
        
        # スピーカー情報の確認
        if not speakers:
            error_msg = "利用可能なスピーカー情報がありません。COEIROINKサーバーの起動に失敗している可能性があります。"
            print(error_msg)
            return {"error": error_msg}, 400
        
        print(f"利用可能なスピーカー数: {len(speakers)}")
        
        # 同じ階層のtext.txtを再度読み込む
        file_path = get_text_file_path()
        print(f"テキストファイルのパス: {file_path}")
        
        if not os.path.exists(file_path):
            error_msg = f"テキストファイルが見つかりません: {file_path}"
            print(error_msg)
            return {"error": error_msg}, 400
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        print(f"テキストファイルの内容（最初の100文字）: {text_content[:100]}...")
        
        lines = parse_text_content(text_content)
        
        if not lines:
            error_msg = "合成するデータがありません。text.txtの形式を確認してください。"
            print(error_msg)
            return {"error": error_msg}, 400
        
        print(f"解析された行数: {len(lines)}")
        
        output_path, error = synthesize_dialogue(lines, speakers)
        if error:
            print(f"音声合成エラー: {error}")
            return {"error": error}, 400
            
        print(f"音声合成成功: {output_path}")
        return {"success": True, "file_path": output_path}
        
    except Exception as e:
        error_msg = f"予期せぬエラーが発生しました: {str(e)}"
        print(error_msg)
        import traceback
        print(f"エラーの詳細:\n{traceback.format_exc()}")
        return {"error": error_msg}, 500

@app.route("/audio/<path:filename>")
def get_audio(filename):
    """生成された音声ファイルを提供"""
    output_dir = get_output_directory()
    return send_file(os.path.join(output_dir, filename))

if __name__ == "__main__":
    try:
        # templatesディレクトリが存在しない場合は作成
        os.makedirs("templates", exist_ok=True)
        
        # HTMLテンプレートを作成
        with open("templates/index.html", "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>音声合成アプリ</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .dialogue-line { margin: 10px 0; padding: 10px; border: 1px solid #ccc; }
        .controls { margin: 20px 0; }
        button { padding: 10px 20px; background: #4CAF50; color: white; border: none; cursor: pointer; margin: 5px; }
        button:hover { background: #45a049; }
        #status { margin: 10px 0; padding: 10px; }
        .success { background: #dff0d8; color: #3c763d; }
        .error { background: #f2dede; color: #a94442; }
    </style>
</head>
<body>
    <h1>音声合成アプリ</h1>
    <div id="status"></div>
    
    <div class="controls">
        <button onclick="synthesize()" id="synthesizeButton">音声を合成</button>
    </div>
    
    <div id="dialogue"></div>

    <script>
        let currentLines = {{ lines|tojson|safe if lines else '[]' }};
        
        function showStatus(message, isError = false) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = isError ? 'error' : 'success';
        }
        
        function updateDialogueDisplay() {
            const dialogueDiv = document.getElementById('dialogue');
            dialogueDiv.innerHTML = currentLines.map(line => `
                <div class="dialogue-line">
                    <p>テキスト: ${line.text}</p>
                    <p>話者: ${line.id === 0 ? "男性" : "つくよみ"}</p>
                    <p>ピッチ: ${line.pitch}</p>
                    <p>速度: ${line.speed}</p>
                </div>
            `).join('');
        }

        // ページ読み込み時に会話データを表示
        window.onload = function() {
            {% if error %}
                showStatus('{{ error }}', true);
            {% else %}
                updateDialogueDisplay();
                {% if lines %}
                    showStatus('text.txtを読み込みました！');
                {% endif %}
            {% endif %}
        };

        function synthesize() {
            if (currentLines.length === 0) {
                showStatus('合成するデータがありません', true);
                return;
            }
            
            showStatus('音声を合成中...');
            document.getElementById('synthesizeButton').disabled = true;
            
            fetch('/synthesize', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('synthesizeButton').disabled = false;
                if (data.error) {
                    showStatus('エラー: ' + data.error, true);
                } else {
                    showStatus('音声の合成が完了しました！');
                    // 音声を再生
                    const audio = new Audio('/audio/' + data.file_path.split('/').pop());
                    audio.play();
                }
            })
            .catch(error => {
                document.getElementById('synthesizeButton').disabled = false;
                showStatus('エラーが発生しました: ' + error, true);
            });
        }
    </script>
</body>
</html>""")
    
        app.run(host='0.0.0.0', port=8001, debug=True)
    except KeyboardInterrupt:
        print("アプリケーションを終了しています...")
    finally:
        # COEIROINKプロセスを終了
        if 'coeiroink_process' in globals() and coeiroink_process:
            print("COEIROINKサーバーを終了しています...")
            coeiroink_process.terminate()
            try:
                coeiroink_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                coeiroink_process.kill()
            print("COEIROINKサーバーが終了しました")