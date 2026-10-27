import functools
import glob
import os
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Callable, List

import wave

import numpy as np
import yt_dlp
import whisper
import logging
import json

# no Windows, impede que cada chamada ao ffmpeg abra uma janela de console
NO_WINDOW = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}

# nomes que o Windows não aceita como arquivo (com qualquer extensão)
WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{i}' for p in ('COM', 'LPT') for i in range(1, 10)}

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config():
    # o config.json é obrigatório (versionado e embutido no .exe); se faltar, o
    # FileNotFoundError já diz o caminho procurado
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = load_config()

# ponytail: guarda só o último modelo usado (o large ocupa ~3 GB de RAM);
# trocar de modelo recarrega
_load_model = functools.lru_cache(maxsize=1)(whisper.load_model)

def setup_folders():
    os.makedirs(CONFIG['storage'], exist_ok=True)
    os.makedirs(CONFIG['audio_folder'], exist_ok=True)
    os.makedirs(CONFIG['text_folder'], exist_ok=True)


def get_whisper_models():
    return list(CONFIG['whisper_models'].keys())


def sanitize_filename(name: str, max_length: int = 100) -> str:
    # mantém apenas caracteres alfanuméricos, espaço, underline e traço
    safe = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in name).strip()
    # se ainda estiver vazio, coloca um nome padrão
    if not safe:
        safe = "audio"
    # trunca sem quebrar palavras (corta no último espaço antes do limite)
    if len(safe) > max_length:
        safe = safe[:max_length].rsplit(' ', 1)[0]
    if safe.upper() in WINDOWS_RESERVED:
        safe += '_'
    return safe


def _unique_path(folder, stem: str, ext: str) -> Path:
    # evita sobrescrever arquivo existente: nome, nome_1, nome_2...
    path = Path(folder) / f"{stem}{ext}"
    counter = 1
    while path.exists():
        path = Path(folder) / f"{stem}_{counter}{ext}"
        counter += 1
    return path


def download_audio(youtube_url: str, output_folder: Optional[str] = None, progress_hook: Optional[Callable] = None) -> str:
    """
    Faz o download do áudio usando yt-dlp para a pasta output_folder (ou CONFIG['audio_folder']).
    Retorna o caminho final do .mp3 salvo (com nome baseado no título do vídeo, sanitizado).
    Em caso de falha, levanta a exceção do yt-dlp.
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

    info = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extrai e baixa em dois passos (é o que o extract_info(download=True)
            # faz por dentro) para já saber o id se o download falhar
            info = ydl.extract_info(youtube_url, download=False)
            info = ydl.process_ie_result(info, download=True)
            # caminho do arquivo originalmente gerado (antes de renomear)
            generated = Path(ydl.prepare_filename(info)).with_suffix('.mp3')
    except Exception as e:
        # repassa o erro: a mensagem do yt-dlp é o que explica a falha para o usuário
        logging.error(f'❌ Erro no download: {e}')
        # remove só o que este vídeo deixou pela metade (<id>.mp4.part, <id>.webm...)
        if info and info.get('id'):
            for leftover in Path(output_folder).glob(f"{glob.escape(info['id'])}.*"):
                leftover.unlink(missing_ok=True)
        raise

    if not generated.exists():
        raise RuntimeError(f'O download terminou, mas o arquivo não foi encontrado: {generated}')

    # tenta nome a partir do título; se não tiver título, usa id
    title = info.get('title') or info.get('id') or generated.stem
    final = _unique_path(output_folder, sanitize_filename(title), '.mp3')
    try:
        shutil.move(str(generated), str(final))
        return str(final)
    except Exception as e:
        logging.error(f'❌ Erro ao renomear arquivo baixado: {e}')
        # como fallback, retorna o caminho gerado original
        return str(generated)


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
        check=True,
        **NO_WINDOW
    )

    return output_path


def process_local_file(file_path: str, output_folder: Optional[str] = None) -> Optional[str]:
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
        ext = path.suffix.lower()
        target = Path(output_folder) / (safe_stem + ext)

        # Se o arquivo de origem já está na pasta de destino com o nome correto
        if path.resolve() == target.resolve():
            return str(target)

        # Caso contrário, copia/converte para a pasta de saída (o original nunca é
        # renomeado nem movido, mesmo que já esteja nessa pasta)
        if ext in ('.mp3', '.wav'):
            target = _unique_path(output_folder, safe_stem, ext)
            shutil.copy2(path, target)
            return str(target)
        else:
            # Converte para WAV
            target_wav = _unique_path(output_folder, safe_stem, '.wav')
            convert_to_wav(path, output_path=target_wav)
            return str(target_wav)
    except Exception as e:
        logging.error(f"Erro no processamento do arquivo local: {e}")
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
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, **NO_WINDOW)
    files = [str(Path(out_dir) / f) for f in os.listdir(out_dir) if f.lower().endswith('.wav')]
    files.sort(key=lambda x: int(Path(x).stem.replace('segment', '')))
    return files


def _load_wav(path: str) -> np.ndarray:
    # os segmentos já saem em WAV 16 kHz mono PCM 16 bits; lendo aqui, o Whisper
    # não precisa chamar o ffmpeg de novo para cada segmento
    with wave.open(path, 'rb') as wf:
        data = wf.readframes(wf.getnframes())
    return np.frombuffer(data, np.int16).astype(np.float32) / 32768.0


def transcribe_audio_with_progress(file_path: str, model_name: str, callback: Optional[Callable[[int, Optional[str]], None]] = None, segment_time: int = 30, language: Optional[str] = None) -> dict:
    """
    Transcreve o áudio. Com language=None, o idioma é detectado no 1º segmento e
    reaproveitado nos demais (o Whisper faz o mesmo com o arquivo inteiro).
    Retorna {'text': str, 'segments': [(início_s, fim_s, texto), ...]}, com os
    tempos relativos ao áudio inteiro.
    """
    model = _load_model(model_name)
    timed = []

    # a pasta dos segmentos some ao sair do bloco, mesmo se a transcrição falhar
    with tempfile.TemporaryDirectory(prefix='tmp_segments_', ignore_cleanup_errors=True) as tmp_dir:
        try:
            segments = _split_audio_to_segments(file_path, tmp_dir, segment_time=segment_time)
        except Exception:
            segments = []

        if not segments:
            # fallback: transcreve o arquivo inteiro, sem segmentação
            if callback:
                callback(0, 'Transcrevendo (sem segmentação)...')
            r = model.transcribe(file_path, language=language, verbose=False, fp16=False)
            text = r['text']
            timed = [(s['start'], s['end'], s['text'].strip()) for s in r.get('segments', [])]
        else:
            full_text_parts = []
            offset = 0.0
            total = len(segments)
            for idx, seg in enumerate(segments):
                if callback:
                    callback(int((idx / total) * 100), f'Transcrevendo segmento {idx + 1}/{total}...')
                audio = _load_wav(seg)
                try:
                    r = model.transcribe(audio, language=language, verbose=False, fp16=False)
                    language = language or r.get('language')
                    seg_text = r.get('text', '')
                    timed += [(offset + s['start'], offset + s['end'], s['text'].strip()) for s in r.get('segments', [])]
                except Exception as e:
                    seg_text = f'\n[Erro ao transcrever segmento {idx + 1}: {e}]\n'
                full_text_parts.append(seg_text)
                # duração real do segmento (o ffmpeg não corta exatamente no segment_time)
                offset += len(audio) / 16000
                if callback:
                    callback(int(((idx + 1) / total) * 100), f'Transcrevendo segmento {idx + 1}/{total}...')
            text = "\n".join(full_text_parts)

    if callback:
        callback(100, 'Transcrição concluída')

    return {'text': text, 'segments': timed}


def _srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(segments) -> str:
    """Monta a legenda .srt a partir de [(início_s, fim_s, texto), ...]."""
    blocks = []
    for i, (start, end, text) in enumerate((s for s in segments if s[2]), 1):
        blocks.append(f"{i}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
    return "\n".join(blocks)