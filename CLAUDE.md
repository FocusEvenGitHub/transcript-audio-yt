# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

App desktop (PyQt5) que transcreve áudio de vídeo do YouTube, de arquivo local ou
do microfone com o Whisper. Detalhes de uso ficam no `README.md`.

## Stack (conferida)

- Python 3.10.11 (`venv/`, Windows; o `python` padrão da máquina é o 3.14,
  por isso o `run.bat` usa `py -3.10`). Dependências no `requirements.txt`, com
  as versões testadas fixadas (o yt-dlp fica com `>=`).
- O `venv` atual tem PyQt5 5.15.11, yt-dlp 2026.3.17, numpy 2.2.6,
  openai-whisper 20250625, sounddevice 0.5.6 e torch 2.14.1+cpu.
- FFmpeg no PATH (chamado via `subprocess` para converter e dividir o áudio).
- Empacotamento com PyInstaller (`app.spec`, onefile, `icone.ico`).
  `AudioTranscriber.spec` é um spec antigo, gerado sem hiddenimports.

## Arquitetura (conferida)

Duas camadas, só isso:

- `app.py` — a interface. `MainApp` (janela), `Worker(QThread)` (download ou
  arquivo local → transcrição → grava o `.txt`) e `Recorder(QThread)` (grava WAV
  com o `sounddevice`). A gravação é desligada sozinha se o `sounddevice` ou o
  PortAudio faltarem (`RECORDING_AVAILABLE`).
- `youtube_audio_to_text.py` (importado como `yt`) — a lógica: carrega o
  `config.json` em `CONFIG` na importação, `download_audio` (yt-dlp com o
  cliente `android`; salva como `<id>.mp3` e renomeia para o título
  sanitizado), `process_local_file` (copia mp3/wav, converte o resto para WAV
  16 kHz mono; nunca move nem renomeia o original), `transcribe_audio_with_progress`
  (divide com `ffmpeg -f segment` num `TemporaryDirectory` do sistema, transcreve
  segmento a segmento com o idioma detectado no 1º e repassa o progresso por
  callback). O `download_audio` levanta a exceção do yt-dlp em caso de falha.
  O `Recorder` salva `gravacao_YYYYMMDD_HHMMSS.wav` direto na pasta de áudio.

O `Worker` só conversa com a UI por sinais (`progress`, `status`, `finished`,
`error`); não mexa em widgets de dentro da thread.

Arquivos auxiliares: o `config.json` define as pastas (`storage/audio`,
`storage/text`), os formatos aceitos, as tentativas de download e o mapa de
nome de exibição → modelo do Whisper. O log vai para `app.log` no diretório
atual. O `cookies.txt` (opcional, **fora do git**) é procurado ao lado do
módulo e depois no diretório atual.

## Comandos

```bash
run.bat                    # Windows: cria o venv se faltar, instala o requirements e roda o app
./run.sh                   # Linux: o mesmo
venv\Scripts\activate
python app.py              # roda o app
pyinstaller app.spec       # gera dist/app.exe (com o venv ativado)
```

Nesta sessão do Claude Code o `cmd` tem `NoDefaultCurrentDirectoryInExePath=1`:
chame `.\run.bat`, porque `run.bat` sozinho dá "não reconhecido".

Não tem testes, lint, análise estática nem CI. Também não tem Docker.

## Convenções observadas

- Comentários, mensagens da UI e status em português. Nenhum formatador
  configurado.
- Nomes de arquivo passam por `sanitize_filename`, e colisões viram `_1`, `_2`…

## Regras de segurança

- Nunca ler, imprimir nem commitar o `cookies.txt`: são cookies de sessão do
  YouTube/Google. Ele também não entra no `app.spec` (iria dentro do .exe).
- Não ler `.env` nem segredos. Commit e push só quando pedirem.
- Sem banco de dados neste projeto.

## Fluxo de versão e documentação

Ainda **não existem** `ROADMAP.md` nem `CHANGELOG.md`, então não há fonte de
versão. Enquanto não existirem, não invente versão nem tag. Quando forem
criados, o CHANGELOG e os docs (README, ROADMAP) são atualizados no mesmo passe,
no mesmo PR, e tag só com confirmação.

## Board no Trello

O padrão FocusEven pede um board espelhando o ROADMAP. Como ainda não há
ROADMAP, ainda não há board definido.

## Regras gerais

- Sem dependência nova nem bump de versão sem pedido. Nunca dizer que um teste
  passou sem ter rodado.
- Divergências conhecidas entre código e doc (aponte, não corrija em silêncio):
  - `load_config()` tenta criar o `config.json` a partir do placeholder
    `{ ... }`, que quebra no `json.dump`. O README documenta o `config.json`
    como obrigatório.
  - O `.gitignore` ignora `YoutubeAudios/*`, mas 4 transcrições dessa pasta
    continuam versionadas.

## Windows e Linux

O app tem que funcionar nos dois. Os pontos que dependem do sistema operacional:
`NO_WINDOW` nas chamadas ao ffmpeg, os textos de ajuda da gravação
(`IS_WINDOWS`), a gravação na taxa nativa do dispositivo, o stdout/stderr nulos
no .exe sem console e a pasta do app colocada na frente do `PATH`.

Armadilhas do Windows, conferidas:
- O `youtube_audio_to_text` (que importa whisper/torch) tem que ser importado
  **antes** do PyQt5. Na ordem inversa, o torch falha com WinError 1114 no
  `c10.dll`.
- O WASAPI só abre stream numa thread com COM inicializado; por isso o
  `Recorder.run` chama `CoInitializeEx`.
- No .exe a ordem dos imports não basta, porque o hook do PyQt5 põe o
  `Qt5\bin` (com o `msvcp140.dll` 14.26) na busca de DLLs. O `app.spec` troca
  todas as cópias do runtime do VC++ pelas do `System32` de quem gera o build,
  e empacota os assets do Whisper (`collect_data_files('whisper')`).
