import os
import re
import time
from datetime import datetime
from flask import Flask, render_template, request, send_file
from google.cloud import texttospeech

# 音声ファイル結合用
try:
    from pydub import AudioSegment
    AUDIO_MERGE_AVAILABLE = True
except ImportError:
    AUDIO_MERGE_AVAILABLE = False
    print("pydub not available, using simple concatenation")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

VOICE_ID_man = 0
VOICE_ID_woman = 1

OUTPUT_DIR = os.environ.get('AUDIO_OUTPUT_DIR', 'audio_output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_text(text):
    return re.sub(r'^セリフ:\s*', '', text).strip()

def get_text_file_path():
    return os.path.join(os.path.dirname(__file__), "text.txt")

def generate_filename():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"voice_dialogue_{timestamp}.mp3"

def synthesize_text_google_tts(text, speaker_id=0):
    """Google Cloud TTS で音声生成"""
    try:
        client = texttospeech.TextToSpeechClient()
        # 話者に応じて声を選択
        if speaker_id == VOICE_ID_man:
            voice_name = "ja-JP-Wavenet-A"
        else:
            voice_name = "ja-JP-Wavenet-C"

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="ja-JP",
            name=voice_name
        )
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        temp_filename = f"temp_google_{int(time.time()*1000)}_{speaker_id}.mp3"
        temp_filepath = os.path.join(OUTPUT_DIR, temp_filename)

        with open(temp_filepath, "wb") as out:
            out.write(response.audio_content)

        return temp_filepath
    except Exception as e:
        print(f"Google TTS synth failed: {e}")
        return None

def synthesize_text(text, speaker_id=0):
    """Google TTS のみを使用"""
    return synthesize_text_google_tts(text, speaker_id)

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
            print(f"pydub結合に失敗: {e}")
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
                speaker_id = VOICE_ID_man if current_speaker == "男性" else VOICE_ID_woman
                lines.append({"text": " ".join(current_text), "id": speaker_id})
                current_text = []
            current_speaker = speaker_match.group(1)
            continue
        if current_speaker is not None:
            current_text.append(text)

    if current_speaker is not None and current_text:
        speaker_id = VOICE_ID_man if current_speaker == "男性" else VOICE_ID_woman
        lines.append({"text": " ".join(current_text), "id": speaker_id})

    return lines

@app.route("/")
def index():
    try:
        file_path = get_text_file_path()
        if not os.path.exists(file_path):
            return render_template("index.html", error="text.txtが見つかりません")
        with open(file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        lines = parse_text_content(text_content)
        return render_template("index.html", lines=lines)
    except Exception as e:
        return render_template("index.html", error=f"エラー: {e}")

@app.route("/synthesize", methods=["POST"])
def synthesize():
    try:
        file_path = get_text_file_path()
        if not os.path.exists(file_path):
            return {"error": "text.txtがありません"}, 400
        with open(file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        lines = parse_text_content(text_content)
        if not lines:
            return {"error": "合成するデータがありません"}, 400

        temp_files = []
        for line in lines:
            cleaned_text = clean_text(line["text"])
            print(f"音声生成中: {cleaned_text} (話者: {'男性' if line['id']==VOICE_ID_man else '女性'})")
            audio_path = synthesize_text(cleaned_text, line["id"])
            if audio_path:
                temp_files.append(audio_path)
                print(f"音声生成成功: {audio_path}")
            else:
                print(f"音声生成失敗: {cleaned_text}")

        if not temp_files:
            return {"error": "音声生成に失敗しました"}, 500

        output_filename = generate_filename()
        final_audio_path = os.path.join(OUTPUT_DIR, output_filename)
        combined_path = combine_audio_files(temp_files, final_audio_path)

        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"一時ファイル削除エラー: {e}")

        if not combined_path:
            return {"error": "音声ファイルの結合に失敗しました"}, 500

        return {"success": True, "combined_filename": os.path.basename(combined_path)}
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"error": f"予期せぬエラー: {e}"}, 500

@app.route("/audio/<path:filename>")
def get_audio(filename):
    fp = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(fp):
        return "Not found", 404
    return send_file(fp, mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8001, debug=True)
