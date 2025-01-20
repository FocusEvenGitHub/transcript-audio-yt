from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QLineEdit, QLabel, QWidget, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt
import youtube_audio_to_text  # Importa o script com a lógica

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Audio to Text")
        self.setGeometry(200, 200, 400, 200)

        # Layout
        layout = QVBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Digite a URL do vídeo do YouTube aqui")
        layout.addWidget(QLabel("URL do vídeo do YouTube:"))
        layout.addWidget(self.url_input)

        self.output_folder_btn = QPushButton("Escolher pasta de saída")
        self.output_folder_btn.clicked.connect(self.choose_output_folder)
        layout.addWidget(self.output_folder_btn)

        self.output_folder_label = QLabel("Pasta de saída: Não selecionada")
        layout.addWidget(self.output_folder_label)

        transcribe_btn = QPushButton("Iniciar Transcrição")
        transcribe_btn.clicked.connect(self.start_transcription)
        layout.addWidget(transcribe_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.output_folder = None

    def choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Escolha a pasta de saída")
        if folder:
            self.output_folder = folder
            self.output_folder_label.setText(f"Pasta de saída: {folder}")

    def start_transcription(self):
        url = self.url_input.text()
        if not url:
            QMessageBox.warning(self, "Erro", "Por favor, insira a URL do vídeo.")
            return
        if not self.output_folder:
            QMessageBox.warning(self, "Erro", "Por favor, selecione uma pasta de saída.")
            return

        self.status_label.setText("Baixando áudio...")
        try:
            audio_path = youtube_audio_to_text.download_audio(url, self.output_folder)
            self.status_label.setText("Transcrevendo áudio...")
            transcribed_text = youtube_audio_to_text.transcribe_audio(audio_path)
            self.status_label.setText("Transcrição concluída!")

            # Salvar transcrição em um arquivo .txt
            output_text_file = audio_path.replace('.mp3', '.txt')
            with open(output_text_file, 'w', encoding='utf-8') as f:
                f.write(transcribed_text)

            QMessageBox.information(self, "Sucesso", f"Transcrição salva em:\n{output_text_file}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro: {str(e)}")
            self.status_label.setText("Erro durante o processo.")

if __name__ == "__main__":
    app = QApplication([])
    window = MainApp()
    window.show()
    app.exec_()
 