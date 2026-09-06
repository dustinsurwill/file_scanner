from dataclasses import dataclass

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QColorDialog, QDialog, QGridLayout, QLineEdit, QPushButton


@dataclass
class ScanDisplayOptions:
    found_color: QColor
    missing_color: QColor
    invalid_regex_background: QColor
    invalid_regex_text: QColor
    error_color: QColor
    found_text: str = 'true'
    missing_text: str = 'false'
    error_text: str = 'ERROR'


class Options(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.display = ScanDisplayOptions(
            found_color=QColor('green'),
            missing_color=QColor('red'),
            # A fixed, deliberately theme-independent pair (not just a
            # background) so the invalid-regex warning stays legible in dark
            # mode too - relying on the OS/theme text color against a fixed
            # light background is what caused the original contrast bug.
            invalid_regex_background=QColor('#f8d7da'),
            invalid_regex_text=QColor('#721c24'),
            error_color=QColor('orange'),
        )
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
        self.invalid_regex_background_button = QPushButton('Invalid Regex Background Selector')
        self.invalid_regex_background_button.clicked.connect(self.select_invalid_regex_background)
        self.invalid_regex_background_button.setAutoFillBackground(True)
        self.invalid_regex_background_button.setFlat(True)
        self._apply_button_color(self.invalid_regex_background_button, self.display.invalid_regex_background)
        main_layout.addWidget(self.invalid_regex_background_button, 2, 0, 1, 1)
        self.invalid_regex_text_button = QPushButton('Invalid Regex Text Selector')
        self.invalid_regex_text_button.clicked.connect(self.select_invalid_regex_text)
        self.invalid_regex_text_button.setAutoFillBackground(True)
        self.invalid_regex_text_button.setFlat(True)
        self._apply_button_color(self.invalid_regex_text_button, self.display.invalid_regex_text)
        main_layout.addWidget(self.invalid_regex_text_button, 2, 1, 1, 1)
        self.error_color_button = QPushButton('Scan Error Color Selector')
        self.error_color_button.clicked.connect(self.select_error_color)
        self.error_color_button.setAutoFillBackground(True)
        self.error_color_button.setFlat(True)
        self._apply_button_color(self.error_color_button, self.display.error_color)
        main_layout.addWidget(self.error_color_button, 3, 0, 1, 1)
        self.error_text_input = QLineEdit(self.display.error_text)
        self.error_text_input.textEdited.connect(self.edit_error_text)
        main_layout.addWidget(self.error_text_input, 3, 1, 1, 1)
        self.setLayout(main_layout)
        self.setWindowTitle('Options')

    @staticmethod
    def _apply_button_color(button: QPushButton, color: QColor):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Button, color)
        button.setPalette(palette)

    def refresh_widgets(self):
        """Reflect self.display (e.g. after loading persisted values) back onto the controls."""
        self._apply_button_color(self.found_color_button, self.display.found_color)
        self._apply_button_color(self.missing_color_button, self.display.missing_color)
        self._apply_button_color(self.invalid_regex_background_button, self.display.invalid_regex_background)
        self._apply_button_color(self.invalid_regex_text_button, self.display.invalid_regex_text)
        self._apply_button_color(self.error_color_button, self.display.error_color)
        self.found_text_input.setText(self.display.found_text)
        self.missing_text_input.setText(self.display.missing_text)
        self.error_text_input.setText(self.display.error_text)

    def edit_missing_text(self):
        self.display.missing_text = self.missing_text_input.text()

    def edit_found_text(self):
        self.display.found_text = self.found_text_input.text()

    def edit_error_text(self):
        self.display.error_text = self.error_text_input.text()

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

    def select_invalid_regex_background(self):
        color = QColorDialog.getColor(self.display.invalid_regex_background, self, 'Invalid Regex Background')
        if color.isValid():
            self.display.invalid_regex_background = color
            self._apply_button_color(self.invalid_regex_background_button, color)

    def select_invalid_regex_text(self):
        color = QColorDialog.getColor(self.display.invalid_regex_text, self, 'Invalid Regex Text')
        if color.isValid():
            self.display.invalid_regex_text = color
            self._apply_button_color(self.invalid_regex_text_button, color)

    def select_error_color(self):
        color = QColorDialog.getColor(self.display.error_color, self, 'Scan Error Color')
        if color.isValid():
            self.display.error_color = color
            self._apply_button_color(self.error_color_button, color)
