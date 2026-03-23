# -*- coding: utf-8 -*-

import os
from pathlib import Path
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QRadioButton, QButtonGroup, QComboBox,
    QProgressBar, QCheckBox, QSpinBox
)

import youtube_audio_to_text as yt


class Worker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, mode, url, local_file, output_folder, model_key, segment_time, same_folder):
        super().__init__()
        self.mode = mode
        self.url = url
        self.local_file = local_file
        self.output_folder = output_folder
        self.model_key = model_key
        self.segment_time = segment_time
        self.same_folder = same_folder

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
                # Validação rápida da URL
                try:
                    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                        ydl.extract_info(self.url, download=False)
                except Exception as e:
                    raise RuntimeError(f'URL inválida ou vídeo não disponível: {e}')
                self.status.emit('Iniciando download...')
                def hook(d):
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
                audio_path = yt.download_audio(self.url, audio_folder, progress_hook=hook)
                if not audio_path:
                    raise RuntimeError('Falha no download.')
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
            self.error.emit(str(e))

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()

        yt.setup_folders()

        self.setWindowTitle('YouTube & Audio to Text')
        self.setGeometry(200, 200, 520, 380)

        # por padrão já apontamos para storage/audio
        self.output_path = yt.CONFIG['audio_folder']
        self.local_file = None
        self.worker = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        self.radio_yt = QRadioButton('YouTube URL')
        self.radio_local = QRadioButton('Arquivo Local')
        self.radio_yt.setChecked(True)

        group = QButtonGroup(self)
        group.addButton(self.radio_yt)
        group.addButton(self.radio_local)

        layout.addWidget(QLabel('Fonte do áudio:'))
        layout.addWidget(self.radio_yt)
        layout.addWidget(self.radio_local)

        self.lbl_url = QLabel('URL do YouTube:')
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText('Cole o link do vídeo aqui')
        layout.addWidget(self.lbl_url)
        layout.addWidget(self.txt_url)

        self.btn_file = QPushButton('Selecionar Arquivo')
        self.lbl_file = QLabel('Nenhum arquivo selecionado')
        layout.addWidget(self.btn_file)
        layout.addWidget(self.lbl_file)

        self.btn_output = QPushButton('Escolher Pasta de Saída')
        self.lbl_output = QLabel(f'Pasta de saída: {self.output_path} (padrão)')
        layout.addWidget(self.btn_output)
        layout.addWidget(self.lbl_output)

        self.same_folder_check = QCheckBox('Salvar texto na mesma pasta do áudio')
        self.same_folder_check.setChecked(False)
        layout.addWidget(self.same_folder_check)

        layout.addWidget(QLabel('Modelo Whisper:'))
        self.model_combo = QComboBox()
        self.model_combo.addItems(yt.get_whisper_models())
        default_model = yt.CONFIG['default_model']
        default_index = list(yt.CONFIG['whisper_models'].values()).index(default_model)
        self.model_combo.setCurrentIndex(default_index)
        layout.addWidget(self.model_combo)

        # SpinBox para duração do segmento
        layout.addWidget(QLabel('Duração do segmento (segundos):'))
        self.segment_spin = QSpinBox()
        self.segment_spin.setRange(10, 600)
        self.segment_spin.setValue(30)
        self.segment_spin.setToolTip('Divide o áudio em segmentos dessa duração para transcrição (menor = mais preciso, maior = mais rápido)')
        layout.addWidget(self.segment_spin)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.btn_transcribe = QPushButton('Transcrever')
        layout.addWidget(self.btn_transcribe)

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
        self.btn_file.clicked.connect(self._select_local_file)
        self.btn_output.clicked.connect(self._select_output_folder)
        self.btn_transcribe.clicked.connect(self._start)

    def _update_mode(self):
        is_yt = self.radio_yt.isChecked()
        self.lbl_url.setVisible(is_yt)
        self.txt_url.setVisible(is_yt)
        self.btn_file.setVisible(not is_yt)
        self.lbl_file.setVisible(not is_yt)

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
        mode = 'yt' if self.radio_yt.isChecked() else 'local'
        url = self.txt_url.text().strip() if mode == 'yt' else ''
        model_key = self.model_combo.currentText()
        segment_time = self.segment_spin.value()
        same_folder = self.same_folder_check.isChecked()

        self.btn_transcribe.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText('Iniciando...')

        self.worker = Worker(
            mode, url, self.local_file, self.output_path,
            model_key, segment_time, same_folder
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self._on_status)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, p: int):
        if not self.progress_bar.isVisible():
            self.progress_bar.setVisible(True)
        # Garante que valores negativos não apareçam
        self.progress_bar.setValue(max(0, min(p, 100)))

    def _on_status(self, s: str):
        self.lbl_status.setText(s)
        QApplication.processEvents()

    def _on_finished(self, out_path: str):
        self.progress_bar.setVisible(False)
        self.btn_transcribe.setEnabled(True)
        QMessageBox.information(self, 'Sucesso', f'Salvo em:\n{out_path}')
        self.lbl_status.setText('Pronto')

    def _on_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.btn_transcribe.setEnabled(True)
        QMessageBox.critical(self, 'Erro', msg)
        self.lbl_status.setText('Erro')


if __name__ == '__main__':
    app = QApplication([])
    window = MainApp()
    window.show()
    app.exec_()