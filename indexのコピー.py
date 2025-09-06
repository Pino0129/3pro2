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
app.secret_key = 'your-secret-key-here'  # フラッシュメッセージ用

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

def get_speakers():
    """利用可能なスピーカー情報を取得する"""
    try:
        response = requests.get("http://localhost:50032/v1/speakers")
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

# グローバル変数としてスピーカー情報を保持
speakers = get_speakers()
if not speakers:
    print("Failed to get speaker information. Exiting...")
    exit(1)

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

def check_coeiroink_server():
    """COEIROINKサーバーの状態を確認する"""
    try:
        response = requests.get("http://localhost:50032/v1/speakers", timeout=5)
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
                    "http://localhost:50032/v1/synthesis",
                    json=synthesis_params,
                    headers={"Content-Type": "application/json", "Accept": "audio/wav"},
                    timeout=30
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

        desktop_path = get_desktop_path()
        output_filename = generate_filename()
        output_path = os.path.join(desktop_path, output_filename)
        
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
        # 同じ階層のtext.txtを再度読み込む
        file_path = get_text_file_path()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        lines = parse_text_content(text_content)
        
        if not lines:
            return {"error": "合成するデータがありません"}, 400
        
        output_path, error = synthesize_dialogue(lines, speakers)
        if error:
            return {"error": error}, 400
            
        return {"success": True, "file_path": output_path}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/audio/<path:filename>")
def get_audio(filename):
    """生成された音声ファイルを提供"""
    desktop_path = get_desktop_path()
    return send_file(os.path.join(desktop_path, filename))

if __name__ == "__main__":
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