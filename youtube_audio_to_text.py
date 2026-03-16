import os
import subprocess
import shutil
import time
from pathlib import Path
from typing import Optional, Callable, List

import yt_dlp
import whisper

CONFIG = {
    'storage': 'storage',
    'audio_folder': 'storage/audio',
    'text_folder': 'storage/text',

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
    os.makedirs(CONFIG['storage'], exist_ok=True)
    os.makedirs(CONFIG['audio_folder'], exist_ok=True)
    os.makedirs(CONFIG['text_folder'], exist_ok=True)


def get_whisper_models():
    return list(CONFIG['whisper_models'].keys())


def sanitize_filename(name: str) -> str:
    # mantém apenas caracteres alfanuméricos, espaço, underline e traço
    return "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in name).strip()


def download_audio(youtube_url: str, output_folder: Optional[str] = None, progress_hook: Optional[Callable] = None) -> Optional[str]:
    """
    Faz o download do áudio usando yt-dlp para a pasta output_folder (ou CONFIG['audio_folder']).
    Retorna o caminho final do .mp3 salvo (com nome baseado no título do vídeo, sanitizado).
    Usa cookies.txt ao lado do módulo ou no cwd se existir.
    """
    if output_folder is None:
        output_folder = CONFIG['audio_folder']

    os.makedirs(output_folder, exist_ok=True)

    # procura cookies.txt no mesmo diretório do módulo e também no cwd como fallback
    cookies_path = Path(__file__).parent / "cookies.txt"
    if not cookies_path.exists():
        alt = Path.cwd() / "cookies.txt"
        if alt.exists():
            cookies_path = alt

    # opções do yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        # salva inicialmente com id.ext para evitar problemas; renomeamos depois para o título sanitizado
        'outtmpl': os.path.join(output_folder, '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'retries': CONFIG['download_retries'],
        'quiet': True,
        'no_warnings': True,
        # força IPv4 em alguns ambientes para reduzir 403
        'source_address': '0.0.0.0',
        # tenta usar player android (ajuda com mudanças no player do YouTube)
        'extractor_args': {
            'youtube': {
                'player_client': ['android']
            }
        }
    }

    if cookies_path.exists():
        ydl_opts['cookiefile'] = str(cookies_path)

    if progress_hook:
        ydl_opts['progress_hooks'] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            # caminho do arquivo originalmente gerado (antes de renomear)
            generated = Path(ydl.prepare_filename(info)).with_suffix('.mp3')

            # tenta nome a partir do título; se não tiver título, usa id
            title = info.get('title') or info.get('id') or generated.stem
            safe_title = sanitize_filename(title)
            target = Path(output_folder) / (safe_title + '.mp3')

            # se o arquivo gerado tem outro nome, renomeia para manter o título
            try:
                if generated.exists():
                    # evita sobrescrever arquivo existente: incrementa se necessário
                    final = target
                    counter = 1
                    while final.exists():
                        final = Path(output_folder) / f"{safe_title}_{counter}.mp3"
                        counter += 1
                    generated.rename(final)
                    return str(final)
                else:
                    # se por algum motivo não existe (postprocessor), tenta procurar por arquivos mp3 recentes no output_folder
                    # fallback: retorna generated mesmo (mesmo que não exista) — caller lidará com erro
                    return str(target)
            except Exception as e:
                print(f'❌ Erro ao renomear arquivo baixado: {e}')
                # como fallback, retorna o caminho gerado original
                return str(generated)

    except Exception as e:
        print(f'❌ Erro no download: {e}')
        return None


def convert_to_wav(input_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Converte input_path para WAV 16k mono. Se output_path for fornecido, salva lá.
    """
    if output_path is None:
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


def process_local_file(file_path: str, output_folder: Optional[str] = None) -> Optional[str]:
    """
    Copia/mede o arquivo local para a pasta de saída (ou CONFIG['audio_folder']).
    Mantém o nome original (sanitizado). Se necessário, converte para WAV no output_folder.
    Retorna o caminho no output_folder.
    """
    if output_folder is None:
        output_folder = CONFIG['audio_folder']

    os.makedirs(output_folder, exist_ok=True)

    path = Path(file_path)

    if not path.exists():
        return None

    if path.suffix.lower() not in CONFIG['supported_formats']:
        return None

    try:
        safe_stem = sanitize_filename(path.stem)
        # se já é mp3 ou wav, copia para a pasta de saída com o mesmo nome (sanitizado)
        if path.suffix.lower() in ('.mp3', '.wav'):
            target = Path(output_folder) / (safe_stem + path.suffix.lower())
            # evita sobrescrever: se existir, incrementa
            if target.exists():
                counter = 1
                while True:
                    candidate = Path(output_folder) / f"{safe_stem}_{counter}{path.suffix.lower()}"
                    if not candidate.exists():
                        target = candidate
                        break
                    counter += 1
            shutil.copy2(path, target)
            return str(target)

        # caso precise converter (por exemplo mp4, m4a, avi), converte para wav dentro da pasta de saída
        target_wav = Path(output_folder) / (safe_stem + '.wav')
        # evita sobrescrever
        if target_wav.exists():
            counter = 1
            while True:
                candidate = Path(output_folder) / f"{safe_stem}_{counter}.wav"
                if not candidate.exists():
                    target_wav = candidate
                    break
                counter += 1

        converted = convert_to_wav(path, output_path=target_wav)
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
    tmp_dir = Path(CONFIG['audio_folder']) / f"tmp_segments_{int(time.time())}"
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