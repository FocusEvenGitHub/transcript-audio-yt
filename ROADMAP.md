# ROADMAP — Audio to Text (transcript-audio-yt)

Documento vivo. Cada versão é entregável e executável isoladamente.
Status: `✅ concluído` · `🚧 em andamento` · `⬜ planejado` · `💭 ideia`
Itens: `[x]` existe · `[~]` existe em parte · `[ ]` falta

O que mudou em cada versão está no [CHANGELOG.md](CHANGELOG.md). O board no
Trello espelha este arquivo; quando os dois divergirem, vale este arquivo.

---

## ✅ v0.1 — Base

**Objetivo:** transcrever áudio de três fontes num app desktop.
Histórico do repositório até 26/10/2026 (PR #4).

- [x] Interface PyQt5 com três fontes: URL do YouTube, arquivo local e gravação
- [x] Download do áudio com yt-dlp (cliente `android`, `cookies.txt` opcional)
- [x] Arquivos locais: mp3/wav copiados, os demais convertidos para WAV com o ffmpeg
- [x] Gravação de microfone com `sounddevice`, desligada sozinha sem PortAudio
- [x] Transcrição com Whisper (tiny a large) dividida em segmentos, com barra de progresso
- [x] Saída em `.txt`, em `storage/text` ou ao lado do áudio
- [x] Build com PyInstaller (`app.spec`, onefile)
- [x] `cookies.txt` fora do git

---

## ✅ v0.2 — Windows e Linux

**Objetivo:** o mesmo app funcionando no Windows (direto e como `.exe`) sem
quebrar o Linux, e fácil de rodar. PR #5, 27/10/2026.

- [x] App abre no Windows (ordem dos imports: whisper/torch antes do PyQt5)
- [x] `.exe` funciona: runtime VC++ único, assets do Whisper, stdout/stderr nulos
- [x] ffmpeg sem janela de console; `ffmpeg.exe` ao lado do app tem prioridade
- [x] Gravação no Windows: taxa nativa do dispositivo e COM inicializado (WASAPI)
- [x] Idioma detectado uma vez e reaproveitado nos segmentos
- [x] Original nunca renomeado; erro de download com a mensagem real
- [x] `run.bat` / `run.sh` e `requirements.txt` com as versões testadas
- [x] README reescrito conforme o comportamento real
- [ ] Testado no Linux → movido para a v0.5

---

## ✅ v0.3 — Robustez

**Objetivo:** nada trava, nada vaza, nada some. PR #6, 27/10/2026.

- [x] Botão Cancelar (download e transcrição) e fechar a janela sem derrubar o app
- [x] Modelo do Whisper em cache entre transcrições
- [x] Pastas temporárias e downloads parciais removidos mesmo em caso de erro
- [x] `config.json` obrigatório, com erro claro
- [x] Limpeza: código morto, spec antigo, log e transcrições fora do git

---

## ⬜ v0.4 — Idioma e legendas

**Objetivo:** controlar o idioma e gerar legenda, além do texto.

- [ ] Seletor de idioma na interface (Automático, Português, Inglês…): resolve
      a detecção errada quando o áudio começa com música ou silêncio
- [ ] Exportar `.srt` com marcação de tempo (o Whisper já devolve os segmentos
      com tempo; o deslocamento de cada segmento entra na soma)

---

## ⬜ v0.5 — Linux validado

**Objetivo:** confirmar no Linux o que a v0.2 só testou no Windows.

- [ ] `run.sh` cria o venv e abre o app (Ubuntu)
- [ ] YouTube, arquivo local e gravação (microfone e `monitor`) no Linux
- [ ] Build com PyInstaller no Linux

---

## 💭 Backlog

- Cortar os segmentos no silêncio em vez de em tempo fixo (hoje uma palavra
  pode ser partida na borda do segmento)
- Usar a GPU quando houver CUDA (`fp16=True`)
- Abrir o `.txt` ou a pasta ao terminar
- Arrastar e soltar arquivo na janela
