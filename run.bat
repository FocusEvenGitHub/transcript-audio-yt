@echo off
rem Cria o venv na primeira vez, confere as dependencias e abre o app.
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo Criando o ambiente virtual com Python 3.10...
    py -3.10 -m venv venv || (
        echo Python 3.10 nao encontrado. Instale: https://www.python.org/downloads/release/python-31011/
        pause
        exit /b 1
    )
)

echo Conferindo dependencias (na primeira vez demora: o PyTorch e grande)...
venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt || (
    pause
    exit /b 1
)

where ffmpeg >nul 2>nul || if not exist ffmpeg.exe echo Aviso: ffmpeg nao encontrado. Instale com: winget install Gyan.FFmpeg

venv\Scripts\python app.py
if errorlevel 1 pause
