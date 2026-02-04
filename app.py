# -*- coding: utf-8 -*-

import os
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QRadioButton, QButtonGroup, QComboBox
)

import youtube_audio_to_text as yt


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()

        yt.setup_folders()

        self.setWindowTitle('YouTube & Audio to Text')
        self.setGeometry(200, 200, 500, 320)

        self.output_path = None
        self.local_file = None

        self._build_ui()

    # ---------------- UI ----------------

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

    # ---------------- Logic ----------------

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
            'Mídia (*.mp3 *.wav *.mp4 *.avi *.mov)'
        )
        if path:
            self.local_file = path
            self.lbl_file.setText(Path(path).name)

    def _start(self):
        if not self.output_path:
            QMessageBox.warning(self, 'Aviso', 'Selecione a pasta de saída.')
            return

        try:
            if self.radio_yt.isChecked():
                self._process_youtube()
            else:
                self._process_local()
        except Exception as e:
            QMessageBox.critical(self, 'Erro', str(e))
            self.lbl_status.setText('Erro')

    def _process_youtube(self):
        url = self.txt_url.text().strip()
        if not url:
            raise ValueError('URL inválida.')

        self.lbl_status.setText('Baixando áudio...')
        QApplication.processEvents()

        audio = yt.download_audio(url, self.output_path)
        if not audio:
            raise RuntimeError('Falha no download.')

        self._transcribe(audio)

    def _process_local(self):
        if not self.local_file:
            raise ValueError('Nenhum arquivo selecionado.')

        self.lbl_status.setText('Processando arquivo...')
        QApplication.processEvents()

        audio = yt.process_local_file(self.local_file)
        if not audio:
            raise RuntimeError('Arquivo inválido.')

        self._transcribe(audio)

    def _transcribe(self, audio_path: str):
        self.lbl_status.setText('Transcrevendo...')
        QApplication.processEvents()

        model = yt.CONFIG['whisper_models'][self.model_combo.currentText()]
        text = yt.transcribe_audio(audio_path, model)

        output_file = Path(self.output_path) / (Path(audio_path).stem + '.txt')

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)

        self.lbl_status.setText('Concluído!')
        QMessageBox.information(self, 'Sucesso', f'Salvo em:\n{output_file}')


if __name__ == '__main__':
    app = QApplication([])
    window = MainApp()
    window.show()
    app.exec_()
