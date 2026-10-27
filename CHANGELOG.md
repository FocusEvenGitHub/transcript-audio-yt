# Changelog — Audio to Text (transcript-audio-yt)

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
As versões seguem o [ROADMAP.md](ROADMAP.md), não SemVer. As versões abaixo
ainda não têm tag no git; a tag só é criada com confirmação.

---

## v0.3 — Robustez — 2026-10-27

### Adicionado
- **Botão Cancelar.** No download, para quase na hora; na transcrição, termina
  o segmento atual antes. O download cancelado não deixa arquivo pela metade.
- **Fechar a janela durante uma transcrição** pede confirmação, cancela e
  espera a thread terminar.

### Alterado
- O modelo do Whisper fica em memória entre transcrições (só o último usado):
  transcrever de novo com o mesmo modelo não espera o carregamento.
- O `config.json` é obrigatório; sem ele, o erro mostra o caminho procurado.

### Corrigido
- O app caía ao fechar a janela com uma transcrição rodando
  ("QThread: Destroyed while thread is still running").
- `load_config()` tentava criar o `config.json` a partir de um placeholder e
  quebrava com `TypeError`.

### Removido
- `transcribe_audio()` e `AudioTranscriber.spec`, sem uso.
- `app.log`, `.idea/` e as transcrições de `YoutubeAudios/` saíram do git
  (continuam no disco e estão no `.gitignore`).

---

## v0.2 — Windows e Linux — 2026-10-27

### Adicionado
- **`run.bat` (Windows) e `run.sh` (Linux):** criam o venv na primeira vez
  (Python 3.10 no Windows), instalam o `requirements.txt`, avisam se faltar o
  ffmpeg e abrem o app.
- `requirements.txt` com as versões testadas.
- Um `ffmpeg.exe` colocado ao lado do app tem prioridade sobre o do PATH.
- A lista de dispositivos de gravação mostra a API (`[MME]`, `[Windows WASAPI]`…).

### Alterado
- A gravação usa a taxa nativa do dispositivo; a conversão para 16 kHz fica
  com o ffmpeg.
- O idioma é detectado no 1º segmento e reaproveitado nos demais.
- A gravação é salva na pasta de áudio como `gravacao_YYYYMMDD_HHMMSS.wav`.
- Os textos de ajuda da gravação mudam conforme o sistema (Mixagem estéreo no
  Windows, `monitor` no Linux).
- README reescrito conforme o comportamento real do código.

### Corrigido
- O app não abria no Windows: o `msvcp140.dll` antigo do PyQt5 fazia o torch
  falhar com `WinError 1114`.
- O `.exe` não abria pelo mesmo motivo, e não transcrevia (faltavam os assets
  do Whisper e o tqdm quebrava sem console).
- Uma janela de console piscava a cada chamada ao ffmpeg.
- A gravação por WASAPI falhava (taxa fixa em 16 kHz e COM não inicializado).
- Um arquivo local na pasta de saída era renomeado.
- Uma checagem de URL feita sem cookies reprovava vídeos que baixariam.
- O erro de download não dizia o motivo.
- O modo Gravar podia transcrever o arquivo local escolhido antes.
- Pastas temporárias de segmentos e gravações sobravam no disco.
- Títulos como `CON` ou `COM1` geravam nomes de arquivo inválidos no Windows.

---

## v0.1 — Base — 2026-10-26

Histórico do repositório até o PR #4: interface PyQt5 com YouTube, arquivo
local e gravação; transcrição com Whisper em segmentos com barra de progresso;
build com PyInstaller; `cookies.txt` fora do git.
