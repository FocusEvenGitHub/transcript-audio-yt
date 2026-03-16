# -*- coding: utf-8 -*-

import os
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QRadioButton, QButtonGroup, QComboBox,
    QProgressBar
)

import youtube_audio_to_text as yt

class Worker(QThread):
    progress = pyqtSignal(int)          # percent 0-100
    status = pyqtSignal(str)           # textual status
    finished = pyqtSignal(str)         # output file path
    error = pyqtSignal(str)            # error message

    def __init__(self, mode: str, url: str, local_file: str, output_folder: str, model_key: str):
        super().__init__()
        self.mode = mode
        self.url = url
        self.local_file = local_file
        self.output_folder = output_folder
        self.model_key = model_key

    def run(self):
        try:
            model_name = yt.CONFIG['whisper_models'][self.model_key]
            audio_path = None

            if self.mode == 'yt':
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
                audio_path = yt.download_audio(self.url, self.output_folder, progress_hook=hook)
                if not audio_path:
                    raise RuntimeError('Falha no download.')
            else:
                if not self.local_file:
                    raise RuntimeError('Nenhum arquivo local selecionado.')
                self.status.emit('Processando arquivo local...')
                # process_local_file já retorna caminho do arquivo (convertido se necessário)
                audio_path = yt.process_local_file(self.local_file)
                if not audio_path:
                    raise RuntimeError('Arquivo inválido ou não suportado.')

            # Transcrição com progresso por segmentos
            self.status.emit('Preparando transcrição...')
            def trans_callback(percent, message=None):
                if message:
                    self.status.emit(message)
                self.progress.emit(percent)

            text = yt.transcribe_audio_with_progress(audio_path, model_name, callback=trans_callback)

            out_path = Path(self.output_folder) / (Path(audio_path).stem + '.txt')
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

        self.output_path = None
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
        self.lbl_output = QLabel('Pasta de saída: não definida')

        layout.addWidget(self.btn_output)
        layout.addWidget(self.lbl_output)

        layout.addWidget(QLabel('Modelo Whisper:'))
        self.model_combo = QComboBox()
        self.model_combo.addItems(yt.get_whisper_models())

        default_model = yt.CONFIG['default_model']
        default_index = list(yt.CONFIG['whisper_models'].values()).index(default_model)
        self.model_combo.setCurrentIndex(default_index)

        layout.addWidget(self.model_combo)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
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

    def _start(self):
        if not self.output_path:
            QMessageBox.warning(self, 'Aviso', 'Selecione a pasta de saída.')
            return

        mode = 'yt' if self.radio_yt.isChecked() else 'local'
        url = self.txt_url.text().strip() if mode == 'yt' else ''
        model_key = self.model_combo.currentText()

        self.btn_transcribe.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_status.setText('Iniciando...')

        self.worker = Worker(mode, url, self.local_file, self.output_path, model_key)
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self._on_status)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, p: int):
        self.progress_bar.setValue(p)

    def _on_status(self, s: str):
        self.lbl_status.setText(s)
        QApplication.processEvents()

    def _on_finished(self, out_path: str):
        self.btn_transcribe.setEnabled(True)
        QMessageBox.information(self, 'Sucesso', f'Salvo em:\n{out_path}')
        self.lbl_status.setText('Pronto')

    def _on_error(self, msg: str):
        self.btn_transcribe.setEnabled(True)
        QMessageBox.critical(self, 'Erro', msg)
        self.lbl_status.setText('Erro')


if __name__ == '__main__':
    app = QApplication([])
    window = MainApp()
    window.show()
    app.exec_()