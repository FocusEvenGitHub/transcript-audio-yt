#!/bin/sh
# Cria o venv na primeira vez, confere as dependências e abre o app.
set -e
cd "$(dirname "$0")"

if [ ! -x venv/bin/python ]; then
    echo "Criando o ambiente virtual..."
    "${PYTHON:-python3}" -m venv venv
fi

echo "Conferindo dependências (na primeira vez demora: o PyTorch é grande)..."
venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt

command -v ffmpeg >/dev/null || echo "Aviso: ffmpeg não encontrado. Instale com: sudo apt install ffmpeg"

exec venv/bin/python app.py
