# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('cookies.txt', '.'),
        ('config.json', '.'),
        # Se quiser incluir ffmpeg.exe (descomente e ajuste o caminho)
        # ('ffmpeg.exe', '.')
    ],
    hiddenimports=[
        'torch',
        'tqdm',
        'regex',
        'yt_dlp.extractor',
        'whisper',
        'whisper._download',
        'whisper.audio',
        'whisper.decoding',
        'whisper.model',
        'whisper.tokenizer',
        'whisper.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Para incluir arquivos de dados do torch, se necessário
# torch_datas = collect_data_files('torch')
# a.datas += torch_datas

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icone.ico'],
)