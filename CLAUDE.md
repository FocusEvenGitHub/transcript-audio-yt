# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

App desktop (PyQt5) que transcreve áudio de vídeo do YouTube, de arquivo local ou
do microfone com o Whisper. Detalhes de uso ficam no `README.md`.

## Stack (conferida)

- Python 3.10.11 (`venv/`, Windows; o `python` padrão da máquina é o 3.14,
  por isso o `run.bat` usa `py -3.10`). Dependências no `requirements.txt`, com
  as versões testadas fixadas (o yt-dlp fica com `>=`). O `torch` vem do índice
  só CPU do PyTorch (`--extra-index-url`): no Linux, o do PyPI traz o CUDA e o
  venv vai de ~2 GB para ~6 GB.
- O `venv` atual tem PyQt5 5.15.11, yt-dlp 2026.3.17, numpy 2.2.6,
  openai-whisper 20250625, sounddevice 0.5.6 e torch 2.14.1+cpu.
- FFmpeg no PATH (chamado via `subprocess` para converter e dividir o áudio).
- Empacotamento com PyInstaller (`app.spec`, onefile, `icone.ico`).

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
  segmento a segmento com o idioma escolhido ou detectado no 1º, repassa o
  progresso por callback e devolve `{'text', 'segments'}`, com os tempos
  relativos ao áudio inteiro), `to_srt` (monta a legenda). A lista de idiomas do
  seletor é o `LANGUAGES` do `app.py`. O `download_audio` levanta a exceção do yt-dlp em caso de falha.
  O `Recorder` salva `gravacao_YYYYMMDD_HHMMSS.wav` direto na pasta de áudio.

O `Worker` só conversa com a UI por sinais (`progress`, `status`, `finished`,
`error`, `cancelled`); não mexa em widgets de dentro da thread. O cancelamento é
cooperativo: `cancel()` liga `cancel_requested`, e o hook de download e o
callback de progresso levantam exceção no próximo ponto de checagem. O
`closeEvent` cancela e espera o `Worker` e o `Recorder`. O modelo do Whisper
fica em cache (`_load_model`, só o último usado).

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

A versão vem do `ROADMAP.md` (`v0.1`, `v0.2`…), não de SemVer. Cada PR
atualiza o `CHANGELOG.md` (Keep a Changelog, em português) e os docs (README,
ROADMAP) no mesmo passe, no mesmo PR. A partir da v0.4 (pedido do Henry,
27/10/2026), cada versão ganha tag anotada `v0.N` no commit de merge do `main`,
depois do merge, sem perguntar de novo. A v0.1 a v0.3 ficaram sem tag.

## Board no Trello

Board **Audio to Text (transcript-audio-yt)**, no workspace do Henry:
https://trello.com/b/NPJRxfEN/audio-to-text-transcript-audio-yt

Listas: `📌 Visão & Regras`, `✅ Concluído / Histórico` (um card por versão
fechada), uma lista por versão aberta do ROADMAP (os itens pendentes viram
cards) e `💭 Backlog`. O repositório é a fonte da verdade. Atualize o board
durante o trabalho, sem precisar pedir: card concluído vai para o histórico
quando a versão fecha, e item novo no ROADMAP vira card.

## Regras gerais

- Sem dependência nova nem bump de versão sem pedido. Nunca dizer que um teste
  passou sem ter rodado.
- Quando código e doc divergirem, aponte o conflito em vez de escolher em
  silêncio. O `config.json` é obrigatório: `load_config()` não cria um padrão.

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

Linux, conferido num container `ubuntu:22.04` (o Docker serve só para testar;
não há Dockerfile no repositório), com janela e áudio pelo WSLg:
- O `run.sh` precisa só de `python3 python3-venv ffmpeg libportaudio2`. O build
  com PyInstaller pede também `binutils` (objdump) e `libpython3.10`; o binário
  tem ~585 MB.
- Pelo PortAudio, o PulseAudio aparece como um dispositivo só (`pulse`, via
  `libasound2-plugins`); o `monitor` não vira dispositivo separado. Escolhe-se a
  fonte no `pavucontrol` ou com `PULSE_SOURCE=<saída>.monitor`.
- Ubuntu 24.04+ não traz Python 3.10 (o 26.04 vem com o 3.14, e o
  `numpy==2.2.6` não tem wheel para ele): precisa de `PYTHON=python3.10 ./run.sh`.
