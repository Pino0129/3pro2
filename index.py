import os
import re
import time
from datetime import datetime
from pathlib import Path
import requests
from flask import Flask, render_template, Response, jsonify, send_file

try:
    from pydub import AudioSegment
    AUDIO_MERGE_AVAILABLE = True
except ImportError:
    AUDIO_MERGE_AVAILABLE = False
    print("pydub not available, simple concatenation will be used")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dummy-secret")

# VOICEVOX設定
SPEAKERS = {
    "male": int(os.environ.get("VOICEVOX_MALE_ID", 9)),
    "female": int(os.environ.get("VOICEVOX_FEMALE_ID", 1))
}

# VOICEVOX Engine ホスト（Render環境では service name: voicevox）
VOICEVOX_HOST = os.environ.get("VOICEVOX_HOST", "http://voicevox:50021")

# 音声出力先
OUTPUT_DIR = Path("static/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- ユーティリティ ----------------
def clean_text(text):
    return re.sub(r'^セリフ:\s*', '', text).strip()

def get_text_file_path():
    return os.path.join(os.path.dirname(__file__), "text.txt")

def generate_filename():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"voice_dialogue_{timestamp}.mp3"

def synthesize_text(text, speaker_id):
    r = requests.post(f"{VOICEVOX_HOST}/v1/tts", json={
        "text": text,
        "speaker": speaker_id,
        "format": "wav"
    })
    if r.status_code != 200:
        print("音声生成失敗:", r.text)
        return None
    filename = OUTPUT_DIR / f"{speaker_id}_{int(time.time()*1000)}.wav"
    with open(filename, "wb") as f:
        f.write(r.content)
    return str(filename)

def combine_audio_files(audio_files, output_path):
    if not audio_files:
        return None
    if len(audio_files) == 1:
        import shutil
        shutil.copy2(audio_files[0], output_path)
        return output_path
    if AUDIO_MERGE_AVAILABLE:
        try:
            combined = AudioSegment.empty()
            for audio_file in audio_files:
                if os.path.exists(audio_file):
                    audio = AudioSegment.from_file(audio_file)
                    combined += audio
                    combined += AudioSegment.silent(duration=500)
            combined.export(output_path, format="mp3")
            return output_path
        except Exception as e:
            print(f"pydub結合失敗: {e}")
            import shutil
            shutil.copy2(audio_files[0], output_path)
            return output_path
    else:
        import shutil
        shutil.copy2(audio_files[0], output_path)
        return output_path

def parse_text_content(text_content):
    lines = []
    current_speaker = None
    current_text = []

    for raw in text_content.splitlines():
        text = raw.strip()
        if not text:
            continue
        speaker_match = re.match(r'\[(男性|女性)\]', text)
        if speaker_match:
            if current_speaker is not None and current_text:
                speaker_id = SPEAKERS["male"] if current_speaker=="男性" else SPEAKERS["female"]
                lines.append({"text": " ".join(current_text), "id": speaker_id})
                current_text = []
            current_speaker = speaker_match.group(1)
            continue
        if current_speaker is not None:
            current_text.append(text)
    if current_speaker is not None and current_text:
        speaker_id = SPEAKERS["male"] if current_speaker=="男性" else SPEAKERS["female"]
        lines.append({"text": " ".join(current_text), "id": speaker_id})
    return lines

# ---------------- ルーティング ----------------
@app.route("/")
def index_route():
    file_path = get_text_file_path()
    if not os.path.exists(file_path):
        return Response(json.dumps({"error": "text.txt が存在しません"}, ensure_ascii=False),
                        mimetype="application/json; charset=utf-8"), 404
    with open(file_path, 'r', encoding='utf-8') as f:
        text_content = f.read()
    lines = parse_text_content(text_content)
    return Response(json.dumps({"lines": lines}, ensure_ascii=False),
                    mimetype="application/json; charset=utf-8")

@app.route("/synthesize", methods=["POST"])
def synthesize_route():
    file_path = get_text_file_path()
    if not os.path.exists(file_path):
        return jsonify({"error": "text.txt がありません"}), 400
    with open(file_path, 'r', encoding='utf-8') as f:
        text_content = f.read()
    lines = parse_text_content(text_content)
    if not lines:
        return jsonify({"error": "合成するデータがありません"}), 400

    temp_files = []
    for line in lines:
        text = clean_text(line["text"])
        audio_path = synthesize_text(text, line["id"])
        if audio_path:
            temp_files.append(audio_path)
    if not temp_files:
        return jsonify({"error": "音声生成失敗"}), 500

    output_filename = generate_filename()
    final_audio_path = OUTPUT_DIR / output_filename
    combined_path = combine_audio_files(temp_files, final_audio_path)

    # 一時ファイル削除
    for temp_file in temp_files:
        try: os.remove(temp_file)
        except: pass

    return jsonify({"success": True, "filename": output_filename})

@app.route("/audio/<path:filename>")
def get_audio(filename):
    fp = OUTPUT_DIR / filename
    if not fp.exists():
        return "Not found", 404
    return send_file(fp, mimetype="audio/mpeg")

# ---------------- 起動 ----------------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8001))
    app.run(host="0.0.0.0", port=PORT)
