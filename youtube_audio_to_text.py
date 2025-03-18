import os
import subprocess
import yt_dlp
import whisper
from pathlib import Path

def download_audio(youtube_url, output_folder):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Mode': 'navigate',
        },
        'cookiefile': 'cookies.txt',  # Create this file from your browser
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'ignoreerrors': True,
        'verbose': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            filename = ydl.prepare_filename(info)
            mp3_filename = Path(filename).with_suffix('.mp3')
            return str(mp3_filename)
    except yt_dlp.utils.DownloadError as e:
        print(f"Download failed: {str(e)}")
        return None


def transcribe_audio(file_path):
    """
    Transcribes the audio file into text using Whisper.

    Args:
        file_path (str): The path to the audio file.

    Returns:
        str: Transcribed text.
    """
    try:
        model = whisper.load_model("small") 
        # tiny / base / small / medium / large
        result = model.transcribe(file_path, language="pt")
        return result['text']
    except Exception as e:
        raise RuntimeError(f"Failed to transcribe audio: {e}")


def convert_to_pcm(file_path):
    """
    Converts the audio file to PCM format if required for Whis'per.

    Args:
        file_path (str): The path to the audio file.

    Returns:
        str: Path to the converted PCM file.
    """
    pcm_path = Path(file_path).with_suffix('.pcm')
    command = [
        'ffmpeg', '-i', file_path, '-f', 's16le', '-ac', '1', '-ar', '16000',
        str(pcm_path)
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return str(pcm_path)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg conversion failed: {e.stderr.decode()}") from e


def main():
    """
    Main function to handle user input, download audio, and transcribe it.
    """
    youtube_url = input("Enter the YouTube video URL: ")
    output_folder = "YoutubeAudios"
    os.makedirs(output_folder, exist_ok=True)

    print("Downloading audio...")
    try:
        audio_path = download_audio(youtube_url, output_folder)
        print(f"Audio downloaded to {audio_path}")
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return

    print("Transcribing audio...")
    try:
        transcribed_text = transcribe_audio(audio_path)
        print("Transcription complete.")
        output_text_file = Path(audio_path).with_suffix('.txt')
        with open(output_text_file, 'w', encoding='utf-8') as f:
            f.write(transcribed_text)
        print(f"Transcribed text saved to {output_text_file}")
    except RuntimeError as e:
        print(f"Error during transcription: {e}")


if __name__ == "__main__":
    main()
