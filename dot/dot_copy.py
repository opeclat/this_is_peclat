import sys
import json
import pyperclip
from PyQt5.QtWidgets import QApplication, QWidget, QLabel
from PyQt5.QtGui import QPixmap, QColor, QPainter, QFont
from PyQt5.QtCore import Qt, QTimer
import argparse
import os

# Obter o diretório do script para caminhos relativos
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMAGE = os.path.join(SCRIPT_DIR, 'icons', 'botao_2.png')

# Valores inteiros das flags do Qt5
FRAMELess_HINT = 0x00000800
TOOL_HINT = 0x00000080
STAY_ON_TOP = 0x00040000
WA_TRANSLUCENT = 86
KEEP_ASPECT_RATIO = 1
SMOOTH_TRANSFORMATION = 1
LEFT_BUTTON = 1
RIGHT_BUTTON = 2

class Toast(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint  # pyright: ignore[reportAttributeAccessIssue,reportArgumentType]
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # pyright: ignore[reportAttributeAccessIssue,reportArgumentType]
        self.label = QLabel(text, self)
        self.label.setStyleSheet('''
            QLabel {
                color: #222;
                background: rgba(255,255,255,0.85);
                border-radius: 12px;
                border: 1.5px solid #e0e0e0;
                padding: 9px 18px;
                font-size: 12px;
                font-family: "San Francisco", "Arial", sans-serif;
            }
        ''')
        self.label.adjustSize()
        self.resize(self.label.size())
        self.setFixedSize(self.label.size())
        self.setStyleSheet('QWidget { border-radius: 12px; background: transparent; }')
        QTimer.singleShot(1200, lambda: (self.close(), None)[-1])

    def show_centered(self, parent):
        parent_geom = parent.geometry()
        x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
        y = parent_geom.y() + parent_geom.height() + 12
        self.move(x, y)
        self.show()

class CircularButton(QWidget):
    def __init__(self, variables, image_path):
        super().__init__()
        self.variables = variables
        self.current_index = 0

        # Carregar imagem PNG e redimensionar para 25% do tamanho original
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            raise FileNotFoundError(f"Imagem não encontrada: {image_path}")
        size = pixmap.size()
        new_width = int(size.width() * 0.25)
        new_height = int(size.height() * 0.25)
        self.pixmap = pixmap.scaled(
            new_width, new_height, 
            Qt.KeepAspectRatio, Qt.SmoothTransformation  # pyright: ignore[reportAttributeAccessIssue,reportArgumentType]
        )
        self.setFixedSize(self.pixmap.size())

        # Tornar a janela do formato da imagem (transparente nas áreas do PNG)
        mask = self.pixmap.createMaskFromColor(QColor(0, 0, 0, 0))
        self.setMask(mask)

        # Sem borda, sem barra de título, sempre no topo
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool  # pyright: ignore[reportAttributeAccessIssue,reportArgumentType]
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # pyright: ignore[reportAttributeAccessIssue,reportArgumentType]

        # Exibir imagem
        self.label = QLabel(self)
        self.label.setPixmap(self.pixmap)
        self.label.setGeometry(0, 0, self.pixmap.width(), self.pixmap.height())

        # Permitir arrastar
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:  # pyright: ignore[reportAttributeAccessIssue]
            if self.current_index < len(self.variables):
                pyperclip.copy(self.variables[self.current_index])
                self.show_toast(self.variables[self.current_index])
                self.current_index += 1
                if self.current_index >= len(self.variables):
                    self.close()
            else:
                self.close()
        elif event.button() == Qt.RightButton:  # pyright: ignore[reportAttributeAccessIssue]
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def show_toast(self, text):
        toast = Toast(text, self)
        toast.show_centered(self)

def load_variables(json_path):
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Arquivo de variáveis não encontrado: {json_path}")
    with open(json_path, 'r') as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get("variables", [])
        else:
            return []

def main():
    parser = argparse.ArgumentParser(description="Botão Circular Flutuante PyQt Minimalista")
    parser.add_argument("--variables", "-v", type=str, required=True, help="Arquivo JSON com variáveis")
    args = parser.parse_args()

    variables = load_variables(args.variables)
    image_path = DEFAULT_IMAGE

    app = QApplication(sys.argv)
    btn = CircularButton(variables, image_path)
    btn.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
