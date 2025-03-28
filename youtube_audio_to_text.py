import os
import subprocess
import yt_dlp
import whisper
from pathlib import Path
from typing import Optional

# Configurações globais
CONFIG = {
    'output_folder': "YoutubeAudios",
    'transcriptions_folder': "Transcriptions",
    'whisper_model': "small",  # Modelo padrão (tiny/base/small/medium/large)
    'supported_formats': ['.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.avi', '.mov'],
    'download_retries': 10,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
}

def setup_folders():
    """Cria as pastas necessárias para o armazenamento de arquivos"""
    os.makedirs(CONFIG['output_folder'], exist_ok=True)
    os.makedirs(CONFIG['transcriptions_folder'], exist_ok=True)

def get_valid_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivos"""
    return "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in name)

def download_audio(youtube_url: str) -> Optional[str]:
    """Baixa áudio de um vídeo do YouTube"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(CONFIG['output_folder'], '%(title)s.%(ext)s'),
        'http_headers': {'User-Agent': CONFIG['user_agent']},
        'retries': CONFIG['download_retries'],
        'ignoreerrors': True,
        'verbose': False
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            filename = ydl.prepare_filename(info)
            mp3_filename = Path(filename).with_suffix('.mp3')
            return str(mp3_filename)
    except Exception as e:
        print(f"❌ Erro no download: {str(e)}")
        return None

def convert_audio(input_path: Path) -> Path:
    """Converte arquivo de áudio/vídeo para formato compatível com Whisper"""
    output_path = input_path.with_suffix('.wav')
    try:
        subprocess.run([
            'ffmpeg', '-i', str(input_path),
            '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
            '-y', str(output_path)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except Exception as e:
        raise RuntimeError(f"Falha na conversão do áudio: {str(e)}")

def transcribe_audio(file_path: str, model_name: str = CONFIG['whisper_model']) -> str:
    """Transcreve áudio usando Whisper"""
    try:
        print("🔍 Carregando modelo Whisper...")
        model = whisper.load_model(model_name)
        print("🎤 Iniciando transcrição...")
        result = model.transcribe(file_path, language="pt")
        return result['text']
    except Exception as e:
        raise RuntimeError(f"Erro na transcrição: {str(e)}")

def process_local_file(file_path: str) -> Optional[str]:
    """Processa arquivo local para transcrição"""
    path = Path(file_path)
    
    if not path.exists():
        print("❌ Arquivo não encontrado!")
        return None

    if path.suffix.lower() not in CONFIG['supported_formats']:
        print("❌ Formato de arquivo não suportado!")
        return None

    try:
        # Converte se necessário
        if path.suffix.lower() not in ['.mp3', '.wav']:
            print("🔄 Convertendo arquivo para formato compatível...")
            new_path = convert_audio(path)
            file_to_transcribe = new_path
        else:
            file_to_transcribe = path

        return str(file_to_transcribe)
    except Exception as e:
        print(f"❌ Erro no processamento: {str(e)}")
        return None

def save_transcription(text: str, source_name: str):
    """Salva a transcrição em arquivo de texto"""
    filename = get_valid_filename(source_name) + '.txt'
    output_path = Path(CONFIG['transcriptions_folder']) / filename
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"✅ Transcrição salva em: {output_path}")

def main():
    """Função principal do programa"""
    setup_folders()
    
    print("🎧 Transcrição de Áudio 🎧")
    print("1. Baixar vídeo do YouTube")
    print("2. Usar arquivo local")
    choice = input("Escolha uma opção (1/2): ")

    audio_path = None
    source_name = ""

    if choice == '1':
        youtube_url = input("Cole a URL do vídeo: ")
        print("⏬ Baixando áudio...")
        audio_path = download_audio(youtube_url)
        if audio_path:
            source_name = Path(audio_path).stem
    elif choice == '2':
        local_path = input("Caminho do arquivo local: ")
        processed_path = process_local_file(local_path)
        if processed_path:
            audio_path = processed_path
            source_name = Path(local_path).stem
    else:
        print("❌ Opção inválida!")
        return

    if not audio_path:
        return

    try:
        print("📝 Iniciando transcrição...")
        transcription = transcribe_audio(audio_path)
        save_transcription(transcription, source_name)
    except Exception as e:
        print(f"❌ Erro fatal: {str(e)}")

if __name__ == "__main__":
    main()