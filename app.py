# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QPushButton,
                             QLineEdit, QLabel, QWidget, QFileDialog, QMessageBox,
                             QRadioButton, QButtonGroup, QComboBox)
from PyQt5.QtCore import Qt
import youtube_audio_to_text
from pathlib import Path
import os


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube & Audio to Text")
        self.setGeometry(200, 200, 500, 300)

        # Layout principal
        layout = QVBoxLayout()

        # Seletor de modo de entrada
        self.input_mode_group = QButtonGroup(self)
        self.radio_yt = QRadioButton("YouTube URL")
        self.radio_local = QRadioButton("Arquivo Local")
        self.input_mode_group.addButton(self.radio_yt)
        self.input_mode_group.addButton(self.radio_local)
        self.radio_yt.setChecked(True)

        layout.addWidget(QLabel("Fonte do áudio:"))
        layout.addWidget(self.radio_yt)
        layout.addWidget(self.radio_local)

        # Campo para URL do YouTube
        self.lbl_url = QLabel("URL do YouTube:")
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Cole o link do vídeo aqui")
        layout.addWidget(self.lbl_url)
        layout.addWidget(self.txt_url)

        # Seletor de arquivo local
        self.btn_file = QPushButton("Selecionar Arquivo")
        self.lbl_file = QLabel("Nenhum arquivo selecionado")
        layout.addWidget(self.btn_file)
        layout.addWidget(self.lbl_file)
        self.btn_file.hide()
        self.lbl_file.hide()

        # Configuração de saída
        self.btn_output = QPushButton("Escolher Pasta de Saída")
        self.lbl_output = QLabel("Pasta de saída: Não definida")
        layout.addWidget(self.btn_output)
        layout.addWidget(self.lbl_output)

        # Configuração do modelo Whisper
        self.setup_model_selection(layout)

        # Botão principal
        self.btn_transcribe = QPushButton("Transcrever Áudio")
        layout.addWidget(self.btn_transcribe)

        # Status
        self.lbl_status = QLabel("Pronto")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        # Configurações iniciais
        self.output_path = None
        self.local_file = None
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Conexões
        self.radio_yt.toggled.connect(self.update_ui_mode)
        self.btn_file.clicked.connect(self.select_local_file)
        self.btn_output.clicked.connect(self.select_output_folder)
        self.btn_transcribe.clicked.connect(self.start_transcription)

    def setup_model_selection(self, layout):
        """Adiciona seletor de modelos do Whisper"""
        # Widget de seleção de modelo
        self.model_label = QLabel("Modelo Whisper:")
        self.model_combo = QComboBox()
        self.model_combo.addItems(youtube_audio_to_text.get_whisper_models())

        # Define o modelo padrão
        default_model = youtube_audio_to_text.CONFIG['default_model']
        default_index = list(youtube_audio_to_text.CONFIG['whisper_models'].values()).index(default_model)
        self.model_combo.setCurrentIndex(default_index)

        # Tooltip com informações
        self.model_combo.setToolTip(
            "Modelos maiores são mais precisos mas mais lentos\n"
            "Tiny: 39M params, Base: 74M, Small: 244M\n"
            "Medium: 769M, Large: 1550M"
        )

        # Adiciona ao layout
        layout.addWidget(self.model_label)
        layout.addWidget(self.model_combo)

    def update_ui_mode(self):
        """Alterna entre os modos de entrada"""
        if self.radio_yt.isChecked():
            self.lbl_url.show()
            self.txt_url.show()
            self.btn_file.hide()
            self.lbl_file.hide()
        else:
            self.lbl_url.hide()
            self.txt_url.hide()
            self.btn_file.show()
            self.lbl_file.show()

    def select_output_folder(self):
        """Seleciona pasta para salvar resultados"""
        folder = QFileDialog.getExistingDirectory(self, "Escolha a pasta de saída")
        if folder:
            self.output_path = folder
            self.lbl_output.setText(f"Pasta de saída: {folder}")

    def select_local_file(self):
        """Seleciona arquivo local para processar"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo",
            "",
            "Arquivos de mídia (*.mp3 *.wav *.mp4 *.avi *.mov);;Todos os arquivos (*)"
        )
        if file_path:
            self.local_file = file_path
            self.lbl_file.setText(f"Arquivo: {Path(file_path).name}")

    def start_transcription(self):
        """Inicia o processo de transcrição"""
        if not self.output_path:
            QMessageBox.warning(self, "Aviso", "Selecione uma pasta de saída!")
            return

        try:
            if self.radio_yt.isChecked():
                self.process_youtube()
            else:
                self.process_local()
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            self.lbl_status.setText("Erro no processo")

    def process_youtube(self):
        """Processa URL do YouTube"""
        url = self.txt_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Aviso", "Insira uma URL válida!")
            return

        self.lbl_status.setText("Baixando áudio...")
        QApplication.processEvents()

        audio_path = youtube_audio_to_text.download_audio(url, self.output_path)
        if not audio_path:
            raise Exception("Falha no download do áudio")

        self.transcribe(audio_path)

    def process_local(self):
        """Processa arquivo local"""
        if not self.local_file:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo!")
            return

        self.lbl_status.setText("Processando arquivo...")
        QApplication.processEvents()

        processed_path = youtube_audio_to_text.process_local_file(self.local_file)
        if not processed_path:
            raise Exception("Formato de arquivo não suportado ou inválido")

        self.transcribe(processed_path)

    def transcribe(self, audio_path):
        """Executa a transcrição e salva o resultado"""
        self.lbl_status.setText("Transcrevendo...")
        QApplication.processEvents()

        # Obtém o modelo selecionado
        model_name = youtube_audio_to_text.CONFIG['whisper_models'][
            self.model_combo.currentText()
        ]

        text = youtube_audio_to_text.transcribe_audio(audio_path, model_name)
        filename = Path(audio_path).stem + ".txt"
        output_file = os.path.join(self.output_path, filename)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)

        self.lbl_status.setText("Concluído!")
        QMessageBox.information(self, "Sucesso", f"Transcrição salva em:\n{output_file}")


if __name__ == "__main__":
    app = QApplication([])
    window = MainApp()
    window.show()
    app.exec_()