# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

App desktop (PyQt5) que transcreve áudio de vídeo do YouTube, de arquivo local ou
do microfone com o Whisper. Detalhes de uso ficam no `README.md`.

## Stack (conferida)

- Python 3.10.11 (`venv/`, Windows). Não tem `requirements.txt`; as dependências
  vêm do README: `PyQt5 yt-dlp openai-whisper sounddevice numpy`.
- O `venv` atual tem PyQt5 5.15.11, yt-dlp 2026.3.17, numpy 2.2.6 e torch, mas
  **não tem** `openai-whisper` nem `sounddevice`: a transcrição e a gravação
  não rodam nele como está.
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
  16 kHz mono), `transcribe_audio_with_progress` (divide com
  `ffmpeg -f segment` em `storage/audio/tmp_segments_*`, transcreve segmento a
  segmento e repassa o progresso por callback).

O `Worker` só conversa com a UI por sinais (`progress`, `status`, `finished`,
`error`); não mexa em widgets de dentro da thread.

Arquivos auxiliares: o `config.json` define as pastas (`storage/audio`,
`storage/text`), os formatos aceitos, as tentativas de download e o mapa de
nome de exibição → modelo do Whisper. O log vai para `app.log` no diretório
atual. O `cookies.txt` (opcional, **fora do git**) é procurado ao lado do
módulo e depois no diretório atual.

## Comandos

```bash
venv\Scripts\activate
python app.py              # roda o app
pyinstaller app.spec       # gera dist/app.exe
```

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
  - O README diz que o `config.json` é criado na primeira execução, mas em
    `load_config()` o padrão é o placeholder `{ ... }`, e sem o `config.json`
    a importação quebra.
  - O exemplo de config no README usa `storage/texts`; o `config.json` real usa
    `storage/text`.
  - O README cita `requirements.txt` e `LICENSE`, que não existem.
  - O `.gitignore` ignora `YoutubeAudios/*`, mas 4 transcrições dessa pasta
    continuam versionadas.
