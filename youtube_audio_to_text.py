import os
import subprocess
from pathlib import Path
from typing import Optional

import yt_dlp
import whisper

CONFIG = {
    'output_folder': 'YoutubeAudios',
    'supported_formats': ['.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.avi', '.mov'],
    'download_retries': 10,
    'user_agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'whisper_models': {
        'Tiny (Mais rápido)': 'tiny',
        'Base': 'base',
        'Small (Recomendado)': 'small',
        'Medium': 'medium',
        'Large (Melhor qualidade)': 'large'
    },
    'default_model': 'small'
}


# ------------------------
# Setup
# ------------------------

def setup_folders():
    os.makedirs(CONFIG['output_folder'], exist_ok=True)


def get_whisper_models():
    return list(CONFIG['whisper_models'].keys())


# ------------------------
# Utils
# ------------------------

def sanitize_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in name)


# ------------------------
# Download YouTube
# ------------------------

def download_audio(youtube_url: str, output_folder: Optional[str] = None) -> Optional[str]:
    if output_folder is None:
        output_folder = CONFIG['output_folder']

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_folder, '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'http_headers': {'User-Agent': CONFIG['user_agent']},
        'retries': CONFIG['download_retries'],
        'quiet': True,
        'no_warnings': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            filename = ydl.prepare_filename(info)
            return str(Path(filename).with_suffix('.mp3'))
    except Exception as e:
        print(f'❌ Erro no download: {e}')
        return None


# ------------------------
# Local file processing
# ------------------------

def convert_to_wav(input_path: Path) -> Path:
    output_path = input_path.with_suffix('.wav')

    subprocess.run(
        [
            'ffmpeg', '-i', str(input_path),
            '-ar', '16000', '-ac', '1',
            '-c:a', 'pcm_s16le',
            '-y', str(output_path)
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )

    return output_path


def process_local_file(file_path: str) -> Optional[str]:
    path = Path(file_path)

    if not path.exists():
        return None

    if path.suffix.lower() not in CONFIG['supported_formats']:
        return None

    try:
        if path.suffix.lower() in ('.mp3', '.wav'):
            return str(path)

        converted = convert_to_wav(path)
        return str(converted)

    except Exception as e:
        print(f'❌ Erro no processamento: {e}')
        return None


# ------------------------
# Transcription
# ------------------------

def transcribe_audio(file_path: str, model_name: str) -> str:
    model = whisper.load_model(model_name)

    result = model.transcribe(
        file_path,
        language='pt',
        verbose=False,
        fp16=False
    )

    return result['text']
