# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.json', '.'),
        # assets do Whisper (mel_filters.npz, tokenizers); sem eles a transcrição falha no .exe
        *collect_data_files('whisper'),
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

# Windows: o PyQt5 traz um runtime do Visual C++ antigo (msvcp140.dll 14.26) e o
# PyInstaller ainda pode pegar outra cópia qualquer do PATH. Com a antiga, o torch
# falha com WinError 1114 no c10.dll. Fica uma cópia só, a do System32 da máquina
# que gera o build (o runtime é retrocompatível, então serve para o Qt também).
if sys.platform == 'win32':
    import os
    vc_runtime = ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')
    system32 = os.path.join(os.environ['WINDIR'], 'System32')
    a.binaries = [b for b in a.binaries if os.path.basename(b[0]).lower() not in vc_runtime]
    a.binaries += [(n, os.path.join(system32, n), 'BINARY') for n in vc_runtime if os.path.exists(os.path.join(system32, n))]

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