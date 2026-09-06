from dataclasses import dataclass

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QColorDialog, QDialog, QGridLayout, QLineEdit, QPushButton


@dataclass
class ScanDisplayOptions:
    found_color: QColor
    missing_color: QColor
    found_text: str = 'true'
    missing_text: str = 'false'


class Options(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.display = ScanDisplayOptions(found_color=QColor('green'), missing_color=QColor('red'))
        main_layout = QGridLayout()
        self.found_color_button = QPushButton('Found Color Selector')
        self.found_color_button.clicked.connect(self.select_found_color)
        self.found_color_button.setAutoFillBackground(True)
        self.found_color_button.setFlat(True)
        self._apply_button_color(self.found_color_button, self.display.found_color)
        main_layout.addWidget(self.found_color_button, 0, 0, 1, 1)
        self.missing_color_button = QPushButton('Missing Color Selector')
        self.missing_color_button.clicked.connect(self.select_missing_color)
        self.missing_color_button.setAutoFillBackground(True)
        self.missing_color_button.setFlat(True)
        self._apply_button_color(self.missing_color_button, self.display.missing_color)
        main_layout.addWidget(self.missing_color_button, 1, 0, 1, 1)
        self.found_text_input = QLineEdit(self.display.found_text)
        self.found_text_input.textEdited.connect(self.edit_found_text)
        main_layout.addWidget(self.found_text_input, 0, 1, 1, 1)
        self.missing_text_input = QLineEdit(self.display.missing_text)
        self.missing_text_input.textEdited.connect(self.edit_missing_text)
        main_layout.addWidget(self.missing_text_input, 1, 1, 1, 1)
        self.setLayout(main_layout)
        self.setWindowTitle('Options')

    @staticmethod
    def _apply_button_color(button: QPushButton, color: QColor):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Button, color)
        button.setPalette(palette)

    def edit_missing_text(self):
        self.display.missing_text = self.missing_text_input.text()

    def edit_found_text(self):
        self.display.found_text = self.found_text_input.text()

    def select_found_color(self):
        color = QColorDialog.getColor(self.display.found_color, self, 'Found Color')
        if color.isValid():
            self.display.found_color = color
            self._apply_button_color(self.found_color_button, color)

    def select_missing_color(self):
        color = QColorDialog.getColor(self.display.missing_color, self, 'Missing Color')
        if color.isValid():
            self.display.missing_color = color
            self._apply_button_color(self.missing_color_button, color)
