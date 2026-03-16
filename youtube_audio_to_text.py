import os
import subprocess
import shutil
import time
from pathlib import Path
from typing import Optional, Callable, List

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


def setup_folders():
    os.makedirs(CONFIG['output_folder'], exist_ok=True)


def get_whisper_models():
    return list(CONFIG['whisper_models'].keys())


def sanitize_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in name)


def download_audio(youtube_url: str, output_folder: Optional[str] = None, progress_hook: Optional[Callable] = None) -> Optional[str]:
    if output_folder is None:
        output_folder = CONFIG['output_folder']

    os.makedirs(output_folder, exist_ok=True)

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

    if progress_hook:
        ydl_opts['progress_hooks'] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            filename = ydl.prepare_filename(info)
            return str(Path(filename).with_suffix('.mp3'))
    except Exception as e:
        print(f'❌ Erro no download: {e}')
        return None


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


def _split_audio_to_segments(input_path: str, out_dir: str, segment_time: int = 30) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    pattern = os.path.join(out_dir, 'segment%04d.wav')
    cmd = [
        'ffmpeg', '-y', '-i', str(input_path),
        '-ar', '16000', '-ac', '1',
        '-f', 'segment', '-segment_time', str(segment_time),
        '-reset_timestamps', '1',
        pattern
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    files = sorted([str(Path(out_dir) / f) for f in os.listdir(out_dir) if f.lower().endswith('.wav')])
    return files


def transcribe_audio_with_progress(file_path: str, model_name: str, callback: Optional[Callable[[int, Optional[str]], None]] = None, segment_time: int = 30) -> str:
    tmp_dir = Path(CONFIG['output_folder']) / f"tmp_segments_{int(time.time())}"
    try:
        segments = _split_audio_to_segments(file_path, str(tmp_dir), segment_time=segment_time)
    except Exception:
        # fallback: try to transcribe whole file without splitting, but still send heartbeats
        model = whisper.load_model(model_name)
        if callback:
            callback(0, 'Transcrevendo (sem segmentação)...')
        result = model.transcribe(file_path, language='pt', verbose=False, fp16=False)
        if callback:
            callback(100, 'Transcrição concluída')
        return result['text']

    if not segments:
        model = whisper.load_model(model_name)
        result = model.transcribe(file_path, language='pt', verbose=False, fp16=False)
        if callback:
            callback(100, 'Transcrição concluída')
        return result['text']

    model = whisper.load_model(model_name)

    full_text_parts = []
    total = len(segments)
    for idx, seg in enumerate(segments):
        if callback:
            callback(int((idx / total) * 100), f'Transcrevendo segmento {idx + 1}/{total}...')
        try:
            r = model.transcribe(seg, language='pt', verbose=False, fp16=False)
            text = r.get('text', '')
        except Exception as e:
            text = f'\n[Erro ao transcrever segmento {idx + 1}: {e}]\n'
        full_text_parts.append(text)
        if callback:
            callback(int(((idx + 1) / total) * 100), f'Transcrevendo segmento {idx + 1}/{total}...')

    try:
        shutil.rmtree(tmp_dir)
    except Exception:
        pass

    if callback:
        callback(100, 'Transcrição concluída')

    return "\n".join(full_text_parts)


def transcribe_audio(file_path: str, model_name: str) -> str:
    model = whisper.load_model(model_name)
    result = model.transcribe(
        file_path,
        language='pt',
        verbose=False,
        fp16=False
    )
    return result['text']