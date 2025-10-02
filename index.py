import os
import re
import time
from datetime import datetime
from pathlib import Path
import requests
from flask import Flask, render_template, jsonify, send_file

from pydub import AudioSegment

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dummy-secret")

# ---------------- VOICEVOX設定 ----------------
SPEAKERS = {
    "male": int(os.environ.get("VOICEVOX_MALE_ID", 13)),
    "female": int(os.environ.get("VOICEVOX_FEMALE_ID", 1))
}
VOICEVOX_HOST = os.environ.get("VOICEVOX_HOST", "http://127.0.0.1:50021")

OUTPUT_DIR = Path("static/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- ユーティリティ ----------------
def clean_text(text):
    return re.sub(r'^セリフ:\s*', '', text).strip()

def get_text_file_path():
    return Path(__file__).parent / "text.txt"

def generate_filename():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"voice_dialogue_{timestamp}.mp3"

def synthesize_text(text, speaker_id):
    """VOICEVOXからWAVを取得してMP3に変換"""
    try:
        r = requests.post(f"{VOICEVOX_HOST}/v1/tts", json={
            "text": text,
            "speaker": speaker_id,
            "format": "wav"
        })
        r.raise_for_status()
    except Exception as e:
        print("音声生成失敗:", e)
        return None

    wav_path = OUTPUT_DIR / f"{speaker_id}_{int(time.time()*1000)}.wav"
    with open(wav_path, "wb") as f:
        f.write(r.content)

    mp3_path = wav_path.with_suffix(".mp3")
    audio = AudioSegment.from_wav(wav_path)
    audio.export(mp3_path, format="mp3")
    wav_path.unlink(missing_ok=True)
    return str(mp3_path)

def combine_audio_files(audio_files, output_path):
    if not audio_files:
        return None
    combined = AudioSegment.empty()
    for audio_file in audio_files:
        combined += AudioSegment.from_file(audio_file)
        combined += AudioSegment.silent(duration=500)
    combined.export(output_path, format="mp3")
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
            if current_speaker and current_text:
                speaker_id = SPEAKERS["male"] if current_speaker=="男性" else SPEAKERS["female"]
                lines.append({"text": " ".join(current_text), "id": speaker_id})
                current_text = []
            current_speaker = speaker_match.group(1)
            continue
        if current_speaker:
            current_text.append(text)
    if current_speaker and current_text:
        speaker_id = SPEAKERS["male"] if current_speaker=="男性" else SPEAKERS["female"]
        lines.append({"text": " ".join(current_text), "id": speaker_id})
    return lines

# ---------------- ルーティング ----------------
@app.route("/")
def index_route():
    return """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>VOICEVOX TTS</title>
</head>
<body>
<h2>VOICEVOX TTSデモ</h2>
<button id="speakBtn">読み上げ</button>
<div id="status"></div>
<script>
document.getElementById("speakBtn").addEventListener("click", () => {
    document.getElementById("status").textContent = "音声を合成中...";
    fetch("/synthesize", { method: "POST" })
      .then(r => r.json())
      .then(data => {
          if(data.success){
              const audio = new Audio(`/audio/${data.filename}`);
              audio.play();
              document.getElementById("status").textContent = "音声の合成が完了しました！";
          } else {
              document.getElementById("status").textContent = "音声生成失敗: " + (data.error || "unknown");
          }
      }).catch(e=>{
          document.getElementById("status").textContent = "エラー: " + e;
      });
});
</script>
</body>
</html>
"""

@app.route("/synthesize", methods=["POST"])
def synthesize_route():
    file_path = get_text_file_path()
    if not file_path.exists():
        return jsonify({"error": "text.txt がありません"}), 400

    text_content = file_path.read_text(encoding="utf-8")
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
    combine_audio_files(temp_files, final_audio_path)

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

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8001))
    app.run(host="0.0.0.0", port=PORT)
