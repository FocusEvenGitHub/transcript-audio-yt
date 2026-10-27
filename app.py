# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
import time
import wave

IS_WINDOWS = os.name == 'nt'

# no .exe sem console (PyInstaller, console=False) stdout/stderr são None, e as
# barras de progresso (tqdm) do Whisper quebram ao escrever neles
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# um ffmpeg colocado ao lado do app (ou do .exe) tem prioridade sobre o do PATH
APP_DIR = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
os.environ['PATH'] = str(APP_DIR) + os.pathsep + os.environ.get('PATH', '')

# tem que vir antes do PyQt5: no Windows o Qt carrega um msvcp140.dll antigo e
# depois o torch (importado pelo whisper) falha com WinError 1114 no c10.dll
import youtube_audio_to_text as yt

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QRadioButton, QButtonGroup, QComboBox,
    QProgressBar, QCheckBox, QSpinBox
)

# Tenta importar sounddevice e numpy; se falhar, desativa gravação
RECORDING_AVAILABLE = False
try:
    import sounddevice as sd
    import numpy as np
    RECORDING_AVAILABLE = True
except (ImportError, OSError) as e:
    print(f"Warning: Could not import sounddevice or PortAudio missing: {e}")

if IS_WINDOWS:
    RECORDING_HELP = 'Gravação indisponível.\nInstale o sounddevice: pip install sounddevice'
else:
    RECORDING_HELP = 'Gravação indisponível.\nInstale o PortAudio: sudo apt install libportaudio2'

# palavras que indicam captura do áudio do sistema (Linux: monitor; Windows: Mixagem estéreo)
LOOPBACK_HINTS = ('monitor', 'stereo mix', 'mixagem')


class Worker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, mode, url, local_file, output_folder, model_key, segment_time, same_folder):
        super().__init__()
        self.mode = mode
        self.url = url
        self.local_file = local_file
        self.output_folder = output_folder
        self.model_key = model_key
        self.segment_time = segment_time
        self.same_folder = same_folder
        self.cancel_requested = False

    def cancel(self):
        # ponytail: o pedido só é atendido no próximo ponto de checagem (progresso
        # do download ou fim de um segmento); carregar o modelo e transcrever sem
        # segmentação não são interrompidos
        self.cancel_requested = True

    def _check_cancel(self):
        if self.cancel_requested:
            raise RuntimeError('Cancelado pelo usuário.')

    def run(self):
        try:
            model_name = yt.CONFIG['whisper_models'][self.model_key]
            audio_path = None

            # Define pasta de áudio (usando output_folder se válido, senão padrão)
            if self.output_folder and os.path.isdir(self.output_folder):
                audio_folder = self.output_folder
            else:
                audio_folder = yt.CONFIG['audio_folder']

            # Define pasta para salvar o texto conforme a escolha do usuário
            if self.same_folder:
                text_folder = audio_folder
            else:
                text_folder = yt.CONFIG['text_folder']

            os.makedirs(text_folder, exist_ok=True)

            # Download ou processamento local
            if self.mode == 'yt':
                self.status.emit('Iniciando download...')
                def hook(d):
                    self._check_cancel()
                    status = d.get('status')
                    if status == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        downloaded = d.get('downloaded_bytes') or 0
                        percent = int(downloaded * 100 / total) if total else 0
                        self.progress.emit(percent)
                        self.status.emit(f"Baixando... {percent}%")
                    elif status == 'finished':
                        self.status.emit('Download concluído. Convertendo...')
                        self.progress.emit(100)
                try:
                    audio_path = yt.download_audio(self.url, audio_folder, progress_hook=hook)
                except Exception as e:
                    raise RuntimeError(f'Falha no download:\n{e}')
            else:
                if not self.local_file:
                    raise RuntimeError('Nenhum arquivo local selecionado.')
                self.status.emit('Processando arquivo local...')
                audio_path = yt.process_local_file(self.local_file, audio_folder)
                if not audio_path:
                    raise RuntimeError('Arquivo inválido ou não suportado.')

            # Transcrição
            self.status.emit('Preparando transcrição...')
            def trans_callback(percent, message=None):
                self._check_cancel()
                if message:
                    self.status.emit(message)
                self.progress.emit(percent)

            text = yt.transcribe_audio_with_progress(
                audio_path, model_name,
                callback=trans_callback,
                segment_time=self.segment_time
            )

            out_path = Path(text_folder) / (Path(audio_path).stem + '.txt')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(text)

            self.status.emit('Concluído!')
            self.progress.emit(100)
            self.finished.emit(str(out_path))

        except Exception as e:
            # o yt-dlp pode embrulhar a exceção do cancelamento; vale o pedido
            if self.cancel_requested:
                self.cancelled.emit()
            else:
                self.error.emit(str(e))


class Recorder(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, device=None, output_folder='.'):
        super().__init__()
        self.recording = False
        self.frames = []
        self.device = device
        self.output_folder = output_folder

    def run(self):
        if not RECORDING_AVAILABLE:
            self.error.emit("Biblioteca de áudio não disponível (PortAudio não instalado).")
            return

        if IS_WINDOWS:
            # o WASAPI exige COM inicializado na thread que abre o stream
            import ctypes
            ctypes.windll.ole32.CoInitializeEx(None, 0)

        self.recording = True
        self.frames.clear()
        self.status.emit('Gravando... Clique em "Parar" quando terminar.')

        def callback(indata, frames, time, status):
            if status:
                self.status.emit(f'Status: {status}')
            if self.recording:
                self.frames.append(indata.copy())

        try:
            # grava na taxa nativa do dispositivo: no Windows (WASAPI) uma taxa
            # diferente da do dispositivo falha. A conversão para 16 kHz fica
            # com o ffmpeg, na hora de dividir o áudio para transcrever.
            samplerate = int(sd.query_devices(self.device, 'input')['default_samplerate'])
            with sd.InputStream(
                samplerate=samplerate, channels=1, callback=callback,
                dtype='int16', device=self.device
            ):
                while self.recording:
                    self.msleep(100)
        except Exception as e:
            self.error.emit(str(e))
            return

        try:
            # salva direto na pasta de áudio, como os downloads: o Worker usa o
            # arquivo onde está e nada sobra no %TEMP%
            os.makedirs(self.output_folder, exist_ok=True)
            out_path = os.path.join(self.output_folder, time.strftime('gravacao_%Y%m%d_%H%M%S.wav'))
            with wave.open(out_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(samplerate)
                wf.writeframes(b''.join(self.frames))
            self.finished.emit(out_path)
        except Exception as e:
            self.error.emit(f"Failed to save recording: {e}")

    def stop(self):
        self.recording = False


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        yt.setup_folders()

        self.setWindowTitle('Audio to Text')
        self.setGeometry(200, 200, 520, 480)  # altura aumentada para a ajuda

        self.output_path = yt.CONFIG['audio_folder']
        self.local_file = None
        self.worker = None
        self.recorder = None
        self.recorded_file = None

        self._build_ui()
        if RECORDING_AVAILABLE:
            self._populate_audio_devices()

    def _build_ui(self):
        layout = QVBoxLayout()

        # --- Fonte do áudio (3 opções) ---
        self.radio_yt = QRadioButton('YouTube URL')
        self.radio_local = QRadioButton('Arquivo Local')
        self.radio_record = QRadioButton('Gravar Áudio')
        self.radio_yt.setChecked(True)

        if not RECORDING_AVAILABLE:
            self.radio_record.setEnabled(False)
            self.radio_record.setToolTip(RECORDING_HELP)

        group = QButtonGroup(self)
        group.addButton(self.radio_yt)
        group.addButton(self.radio_local)
        group.addButton(self.radio_record)

        layout.addWidget(QLabel('Fonte do áudio:'))
        layout.addWidget(self.radio_yt)
        layout.addWidget(self.radio_local)
        layout.addWidget(self.radio_record)

        # --- YouTube URL ---
        self.lbl_url = QLabel('URL do YouTube:')
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText('Cole o link do vídeo aqui')
        layout.addWidget(self.lbl_url)
        layout.addWidget(self.txt_url)

        # --- Arquivo local ---
        self.btn_file = QPushButton('Selecionar Arquivo')
        self.lbl_file = QLabel('Nenhum arquivo selecionado')
        layout.addWidget(self.btn_file)
        layout.addWidget(self.lbl_file)

        # --- Seleção de dispositivo de áudio (aparece apenas no modo Gravar) ---
        self.device_label = QLabel('Dispositivo de áudio:')
        self.device_combo = QComboBox()
        self.device_combo.setToolTip('Escolha o dispositivo de entrada (microfone ou monitor de saída)')
        self.device_combo.setVisible(False)
        layout.addWidget(self.device_label)
        layout.addWidget(self.device_combo)

        # Dica sobre como capturar áudio do sistema
        if IS_WINDOWS:
            device_help = (
                "💡 Para gravar o que está saindo do computador (música, vídeo, etc.),\n"
                "escolha 'Mixagem estéreo' (Stereo Mix). Se não aparecer, ative em\n"
                "Configurações de som > Mais configurações de som > Gravação."
            )
        else:
            device_help = (
                "💡 Para gravar o que está saindo do computador (música, vídeo, etc.),\n"
                "escolha um dispositivo que contenha 'monitor' no nome.\n"
                "Se não houver, selecione 'default' e configure no pavucontrol."
            )
        self.device_help = QLabel(device_help)
        self.device_help.setWordWrap(True)
        self.device_help.setStyleSheet("color: gray; font-size: 10px;")
        self.device_help.setVisible(False)
        layout.addWidget(self.device_help)

        # --- Controles de gravação ---
        self.record_btn = QPushButton('Iniciar Gravação')
        self.stop_btn = QPushButton('Parar Gravação')
        self.stop_btn.setEnabled(False)
        self.record_status = QLabel('')
        self.record_status.setWordWrap(True)
        layout.addWidget(self.record_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.record_status)

        # --- Pasta de saída ---
        self.btn_output = QPushButton('Escolher Pasta de Saída')
        self.lbl_output = QLabel(f'Pasta de saída: {self.output_path} (padrão)')
        layout.addWidget(self.btn_output)
        layout.addWidget(self.lbl_output)

        # --- Mesma pasta ---
        self.same_folder_check = QCheckBox('Salvar texto na mesma pasta do áudio')
        self.same_folder_check.setChecked(False)
        layout.addWidget(self.same_folder_check)

        # --- Modelo Whisper ---
        layout.addWidget(QLabel('Modelo Whisper:'))
        self.model_combo = QComboBox()
        self.model_combo.addItems(yt.get_whisper_models())
        default_model = yt.CONFIG['default_model']
        default_index = list(yt.CONFIG['whisper_models'].values()).index(default_model)
        self.model_combo.setCurrentIndex(default_index)
        layout.addWidget(self.model_combo)

        # --- Duração do segmento ---
        layout.addWidget(QLabel('Duração do segmento (segundos):'))
        self.segment_spin = QSpinBox()
        self.segment_spin.setRange(10, 600)
        self.segment_spin.setValue(30)
        self.segment_spin.setToolTip('Divide o áudio em segmentos para transcrição (menor = mais preciso, maior = mais rápido)')
        layout.addWidget(self.segment_spin)

        # --- Barra de progresso ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # --- Botão transcrever ---
        self.btn_transcribe = QPushButton('Transcrever')
        layout.addWidget(self.btn_transcribe)

        self.btn_cancel = QPushButton('Cancelar')
        self.btn_cancel.setVisible(False)
        layout.addWidget(self.btn_cancel)

        # --- Status ---
        self.lbl_status = QLabel('Pronto')
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self._connect_signals()
        self._update_mode()

    def _connect_signals(self):
        self.radio_yt.toggled.connect(self._update_mode)
        self.radio_local.toggled.connect(self._update_mode)
        self.radio_record.toggled.connect(self._update_mode)
        self.btn_file.clicked.connect(self._select_local_file)
        self.btn_output.clicked.connect(self._select_output_folder)
        self.btn_transcribe.clicked.connect(self._start)
        self.btn_cancel.clicked.connect(self._cancel)
        self.record_btn.clicked.connect(self._start_recording)
        self.stop_btn.clicked.connect(self._stop_recording)

    def _update_mode(self):
        is_yt = self.radio_yt.isChecked()
        is_local = self.radio_local.isChecked()
        is_record = self.radio_record.isChecked()

        self.lbl_url.setVisible(is_yt)
        self.txt_url.setVisible(is_yt)

        self.btn_file.setVisible(is_local)
        self.lbl_file.setVisible(is_local)

        self.record_btn.setVisible(is_record)
        self.stop_btn.setVisible(is_record)
        self.record_status.setVisible(is_record)
        self.device_label.setVisible(is_record)
        self.device_combo.setVisible(is_record)
        self.device_help.setVisible(is_record)

        if not is_record and self.recorder and self.recorder.isRunning():
            self._stop_recording()

    def _select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Escolha a pasta de saída')
        if folder:
            self.output_path = folder
            self.lbl_output.setText(f'Pasta de saída: {folder}')

    def _select_local_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            'Selecionar arquivo',
            '',
            'Mídia (*.mp3 *.wav *.mp4 *.avi *.mov *.m4a *.ogg)'
        )
        if path:
            self.local_file = path
            self.lbl_file.setText(Path(path).name)
            self.lbl_file.setToolTip(path)

    def _start(self):
        if self.radio_yt.isChecked():
            mode = 'yt'
            url = self.txt_url.text().strip()
            local_file = None
            if not url:
                QMessageBox.warning(self, 'Aviso', 'Digite uma URL do YouTube.')
                return
        elif self.radio_record.isChecked():
            mode = 'local'
            url = ''
            local_file = self.recorded_file
            if not local_file:
                QMessageBox.warning(self, 'Aviso', 'Nenhuma gravação disponível.')
                return
        else:
            mode = 'local'
            url = ''
            local_file = self.local_file
            if not local_file:
                QMessageBox.warning(self, 'Aviso', 'Selecione um arquivo local.')
                return

        model_key = self.model_combo.currentText()
        segment_time = self.segment_spin.value()
        same_folder = self.same_folder_check.isChecked()

        self.btn_transcribe.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText('Iniciando...')

        self.worker = Worker(
            mode, url, local_file, self.output_path,
            model_key, segment_time, same_folder
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self._on_status)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.start()

    def _cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)
            self.lbl_status.setText('Cancelando... (termina o trecho atual)')

    def _job_done(self):
        self.progress_bar.setVisible(False)
        self.btn_transcribe.setEnabled(True)
        self.btn_cancel.setVisible(False)

    def _on_progress(self, p: int):
        if not self.progress_bar.isVisible():
            self.progress_bar.setVisible(True)
        self.progress_bar.setValue(max(0, min(p, 100)))

    def _on_status(self, s: str):
        # depois de pedir o cancelamento, o status do worker não sobrescreve o aviso
        if self.worker and not self.worker.cancel_requested:
            self.lbl_status.setText(s)

    def _on_finished(self, out_path: str):
        self._job_done()
        QMessageBox.information(self, 'Sucesso', f'Salvo em:\n{out_path}')
        self.lbl_status.setText('Pronto')

    def _on_error(self, msg: str):
        self._job_done()
        QMessageBox.critical(self, 'Erro', msg)
        self.lbl_status.setText('Erro')

    def _on_cancelled(self):
        self._job_done()
        self.lbl_status.setText('Cancelado')

    def closeEvent(self, event):
        # sem isto, fechar com a thread rodando derruba o app
        # ("QThread: Destroyed while thread is still running")
        if self.worker and self.worker.isRunning():
            answer = QMessageBox.question(
                self, 'Sair', 'Uma transcrição está em andamento. Cancelar e sair?'
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            # ponytail: espera o trecho atual com a janela parada; com modelo grande
            # pode levar alguns segundos
            self.lbl_status.setText('Cancelando...')
            self.worker.cancel()
            self.worker.wait()
        if self.recorder and self.recorder.isRunning():
            self.recorder.stop()
            self.recorder.wait()
        event.accept()

    def _start_recording(self):
        if not RECORDING_AVAILABLE:
            QMessageBox.warning(self, 'Aviso', RECORDING_HELP)
            return

        device_idx = self.device_combo.currentData()
        if device_idx is None:
            device_idx = None

        self.record_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.record_status.setText('Preparando microfone...')
        self.lbl_status.setText('Gravando...')

        self.recorder = Recorder(device=device_idx, output_folder=self.output_path)
        self.recorder.finished.connect(self._recording_finished)
        self.recorder.error.connect(self._on_recording_error)
        self.recorder.status.connect(self.record_status.setText)
        self.recorder.start()

    def _stop_recording(self):
        if self.recorder and self.recorder.isRunning():
            self.recorder.stop()
            self.stop_btn.setEnabled(False)
            self.record_status.setText('Finalizando gravação...')
        else:
            self.record_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.record_status.setText('')

    def _recording_finished(self, file_path):
        self.record_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.record_status.setText(f'Gravação concluída: {Path(file_path).name}')
        self.record_status.setToolTip(file_path)
        self.lbl_status.setText('Gravação concluída. Pressione "Transcrever".')

        # fica separada do arquivo local: cada modo transcreve só o que é seu
        self.recorded_file = file_path

    def _on_recording_error(self, msg):
        self.record_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.record_status.setText('')
        QMessageBox.critical(self, 'Erro na Gravação', msg)
        self.lbl_status.setText('Erro na gravação')

    def _populate_audio_devices(self):
        """Preenche o combo box com dispositivos de entrada, identificando microfones e monitores."""
        self.device_combo.clear()
        try:
            devices = sd.query_devices()
            input_devices = []
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name = dev['name']
                    # Adiciona uma marcação visual para facilitar a escolha
                    if any(h in name.lower() for h in LOOPBACK_HINTS):
                        display_name = f"{name} (monitor - áudio do sistema)"
                    elif 'input' in name.lower() or 'mic' in name.lower() or 'microphone' in name.lower():
                        display_name = f"{name} (microfone)"
                    else:
                        display_name = name
                    # no Windows o mesmo dispositivo aparece uma vez por API
                    # (MME, DirectSound, WASAPI...); o nome da API desfaz a dúvida
                    hostapi = sd.query_hostapis(dev['hostapi'])['name']
                    input_devices.append((i, f"{display_name} [{hostapi}]"))
            if not input_devices:
                self.device_combo.addItem("Nenhum dispositivo de entrada encontrado")
                self.device_combo.setEnabled(False)
                return

            for idx, display_name in input_devices:
                self.device_combo.addItem(display_name, idx)

            # Tenta selecionar o dispositivo padrão do sistema
            default_input = sd.default.device[0] if sd.default.device[0] is not None else None
            if default_input is not None:
                for i in range(self.device_combo.count()):
                    if self.device_combo.itemData(i) == default_input:
                        self.device_combo.setCurrentIndex(i)
                        break
            else:
                # Se não houver padrão, seleciona o primeiro que parece ser um monitor ou o primeiro da lista
                for i in range(self.device_combo.count()):
                    if 'monitor' in self.device_combo.itemText(i).lower():
                        self.device_combo.setCurrentIndex(i)
                        break
        except Exception as e:
            print(f"Erro ao listar dispositivos de áudio: {e}")
            self.device_combo.addItem("Erro ao listar dispositivos")
            self.device_combo.setEnabled(False)


if __name__ == '__main__':
    app = QApplication([])
    window = MainApp()
    window.show()
    app.exec_()