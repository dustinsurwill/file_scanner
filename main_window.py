import re
import sys
from _csv import writer
from functools import partial
from multiprocessing import cpu_count, get_context
from os.path import basename, dirname, isfile

from openpyxl import Workbook
from openpyxl.styles import PatternFill
from PyQt6.QtCore import QSettings, QThread, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from options_dialog import Options
from scanner import MatchMode, ScanResult, scan_files_process

# Recycle each worker after this many files so any per-file memory that a
# parsing library doesn't fully release (observed with pdfminer.six on large
# PDF batches) can't accumulate across the life of a long-running scan.
MAX_TASKS_PER_CHILD = 50
ERROR_CELL_COLOR = QColor('orange')


class ScanWorker(QThread):
    result_ready = pyqtSignal(object)
    finished_scanning = pyqtSignal()

    def __init__(self, keywords, file_names, mode=MatchMode.SUBSTRING, parent=None):
        super().__init__(parent)
        self.keywords = keywords
        self.file_names = file_names
        self.mode = mode
        self._pool = None

    def run(self):
        worker_count = min(cpu_count(), len(self.file_names))
        scan = partial(scan_files_process, self.keywords, mode=self.mode)
        # 'spawn' (not the platform-default 'fork' on Linux) avoids worker
        # processes inheriting this QThread's/QApplication's state, which
        # otherwise deadlocks pool shutdown when a Pool is created from a
        # non-main thread in a Qt app.
        context = get_context('spawn')
        with context.Pool(processes=worker_count, maxtasksperchild=MAX_TASKS_PER_CHILD) as pool:
            self._pool = pool
            try:
                for result in pool.imap_unordered(scan, self.file_names):
                    self.result_ready.emit(result)
            except Exception:  # noqa: BLE001, S110 - a cancel-triggered pool.terminate() surfaces here
                pass
        self.finished_scanning.emit()

    def cancel(self):
        if self._pool is not None:
            self._pool.terminate()


class FileScanner(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        center = QWidget()
        main_layout = QGridLayout(center)
        main_layout.addLayout(self.create_keyword_area(), 0, 0)
        main_layout.setColumnMinimumWidth(0, 350)
        self.file_headers = ['files']
        main_layout.addLayout(self.create_files_area(), 0, 1)
        main_layout.setColumnMinimumWidth(1, 650)
        main_layout.setColumnStretch(1, 1)
        main_layout.setRowMinimumHeight(0, 500)
        self.setCentralWidget(center)
        self.setWindowTitle('File Scanner')
        self.setAcceptDrops(True)
        if sys.platform == 'win32':
            # 'windows11' (Qt 6.7+) supports the Windows dark/light color
            # scheme; 'windowsvista' (Qt's old default) ignores it entirely.
            # Fall back for older Qt/Windows where 'windows11' isn't available.
            QApplication.setStyle(QStyleFactory.create('windows11') or QStyleFactory.create('windowsvista'))
        self.file_names = []
        self.file_rows = {}
        self.scan_errors = []
        self.options = Options(self)
        self.scan_worker = None
        self.progress_dialog = None
        self.settings = QSettings('file-scanner', 'FileScanner')
        geometry = self.settings.value('window_geometry')
        if geometry is not None:
            self.restoreGeometry(geometry)

    def closeEvent(self, event):
        self.settings.setValue('window_geometry', self.saveGeometry())
        super().closeEvent(event)

    def _last_dir(self):
        return self.settings.value('last_dir', '.')

    def _remember_dir(self, path):
        self.settings.setValue('last_dir', dirname(path))

    def create_files_area(self):
        vertical = QVBoxLayout()
        top_buttons = QHBoxLayout()
        self.add_files = QPushButton('Add Files')
        self.add_files.clicked.connect(self.add_files_clicked)
        top_buttons.addWidget(self.add_files)
        self.remove_files = QPushButton('Remove Files')
        self.remove_files.setDisabled(True)
        self.remove_files.clicked.connect(self.remove_files_clicked)
        top_buttons.addWidget(self.remove_files)
        self.export_results = QPushButton('Export to CSV')
        self.export_results.setDisabled(True)
        self.export_results.clicked.connect(self.export_results_clicked)
        top_buttons.addWidget(self.export_results)
        self.export_excel = QPushButton('Export to Excel')
        self.export_excel.setDisabled(True)
        self.export_excel.clicked.connect(self.export_excel_clicked)
        top_buttons.addWidget(self.export_excel)
        vertical.addLayout(top_buttons)
        self.files = QTableWidget()
        self.files.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.files.setAlternatingRowColors(True)
        self.files.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.files.itemSelectionChanged.connect(
            lambda: self.remove_files.setDisabled(not self.files.selectedIndexes())
        )
        self.update_file_headers()
        vertical.addWidget(self.files)
        buttons = QHBoxLayout()
        self.save_keywords = QPushButton('Save Keywords')
        self.save_keywords.clicked.connect(self.save_keywords_clicked)
        self.save_keywords.setDisabled(True)
        buttons.addWidget(self.save_keywords)
        load_keywords = QPushButton('Load Keywords')
        load_keywords.clicked.connect(self.load_keywords_clicked)
        buttons.addWidget(load_keywords)
        options = QPushButton('Options')
        options.clicked.connect(lambda: self.options.show())
        buttons.addWidget(options)
        self.scan_files = QPushButton('Scan Files')
        self.scan_files.setDisabled(True)
        self.scan_files.clicked.connect(self.scan_files_clicked)
        buttons.addWidget(self.scan_files)
        vertical.addLayout(buttons)
        return vertical

    def export_results_clicked(self):
        target_path = QFileDialog.getSaveFileName(self, 'Export Results', self._last_dir(), 'Excel (*.csv)')[0]
        if not target_path:
            return
        self._remember_dir(target_path)
        try:
            with open(target_path, 'wt', newline='') as csv_file:
                csv_writer = writer(csv_file)
                csv_writer.writerow(self.file_headers)
                for row in range(self.files.rowCount()):
                    csv_writer.writerow(
                        [self.files.item(row, 0).text()]
                        + [self.files.item(row, i + 1).text() for i in range(self.keyword_list.count())]
                    )
        except OSError as exc:
            QMessageBox.critical(self, 'Export Failed', f'Could not write results:\n{exc}')

    def export_excel_clicked(self):
        target_path = QFileDialog.getSaveFileName(self, 'Export Results', self._last_dir(), 'Excel Workbook (*.xlsx)')[
            0
        ]
        if not target_path:
            return
        self._remember_dir(target_path)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Results'
        sheet.append(self.file_headers)
        for row in range(self.files.rowCount()):
            values = []
            fills = []
            for column in range(self.files.columnCount()):
                item = self.files.item(row, column)
                values.append(item.text() if item else '')
                fills.append(item.background().color() if item else None)
            sheet.append(values)
            excel_row = row + 2  # header occupies row 1
            for column, color in enumerate(fills, start=1):
                if color is not None and color.isValid() and color.alpha() > 0:
                    hex_color = color.name(QColor.NameFormat.HexRgb).lstrip('#').upper()
                    sheet.cell(row=excel_row, column=column).fill = PatternFill(
                        start_color=hex_color, end_color=hex_color, fill_type='solid'
                    )
        try:
            workbook.save(target_path)
        except OSError as exc:
            QMessageBox.critical(self, 'Export Failed', f'Could not write results:\n{exc}')

    def save_keywords_clicked(self):
        target_path = QFileDialog.getSaveFileName(self, 'Save Keywords', self._last_dir(), 'Text (*.txt)')[0]
        if not target_path:
            return
        self._remember_dir(target_path)
        keywords = [self.keyword_list.item(i).text() for i in range(self.keyword_list.count())]
        try:
            with open(target_path, 'wt') as keywords_file:
                keywords_file.write('\n'.join(keywords) + '\n')
        except OSError as exc:
            QMessageBox.critical(self, 'Save Failed', f'Could not save keywords:\n{exc}')

    def load_keywords_clicked(self):
        source_path = QFileDialog.getOpenFileName(self, 'Load Keywords', self._last_dir(), 'Text (*.txt)')[0]
        if not source_path:
            return
        self._remember_dir(source_path)
        try:
            with open(source_path, 'rt') as keywords_file:
                loaded_keywords = [line for line in keywords_file.read().split('\n') if line]
        except OSError as exc:
            QMessageBox.critical(self, 'Load Failed', f'Could not load keywords:\n{exc}')
            return
        self.keyword_list.addItems(loaded_keywords)
        self._refresh_keyword_validity_highlighting()
        self.update_file_headers()
        if self.keyword_list.count():
            self.save_keywords.setDisabled(False)
        self.update_scan_button_state()

    def _match_mode(self):
        return self.match_mode_combo.currentData()

    def scan_files_clicked(self):
        if not self.file_names:
            return
        keywords = [self.keyword_list.item(i).text().lower() for i in range(self.keyword_list.count())]
        mode = self._match_mode()
        if mode is MatchMode.REGEX:
            for keyword in keywords:
                try:
                    re.compile(keyword)
                except re.error as exc:
                    QMessageBox.critical(
                        self, 'Invalid Regex', f'Keyword "{keyword}" is not a valid regex pattern:\n{exc}'
                    )
                    return
        self.file_rows = {file: row for row, file in enumerate(self.file_names)}
        self.scan_errors = []
        self.scan_files.setDisabled(True)
        self.add_files.setDisabled(True)
        self.progress_dialog = QProgressDialog('Scanning files...', 'Cancel', 0, len(self.file_names), self)
        self.progress_dialog.setWindowTitle('Scanning')
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.scan_worker = ScanWorker(keywords, list(self.file_names), mode, self)
        self.scan_worker.result_ready.connect(self.handle_scan_result)
        self.scan_worker.finished_scanning.connect(self.handle_scan_finished)
        self.progress_dialog.canceled.connect(self.scan_worker.cancel)
        self.scan_worker.start()

    def handle_scan_result(self, result: ScanResult):
        row = self.file_rows[result.file]
        if result.error is not None:
            self.scan_errors.append((result.file, result.error))
            for column in range(1, self.files.columnCount()):
                widget = QTableWidgetItem('ERROR')
                widget.setBackground(ERROR_CELL_COLOR)
                widget.setToolTip(result.error)
                self.files.setItem(row, column, widget)
        else:
            for i, has_match in enumerate(result.matches):
                widget = QTableWidgetItem(self.options.display.found_text if has_match else self.options.display.missing_text)
                widget.setBackground(self.options.display.found_color if has_match else self.options.display.missing_color)
                self.files.setItem(row, i + 1, widget)
        self.progress_dialog.setValue(self.progress_dialog.value() + 1)

    def handle_scan_finished(self):
        self.progress_dialog.close()
        self.update_scan_button_state()
        self.add_files.setDisabled(False)
        self.export_results.setDisabled(False)
        self.export_excel.setDisabled(False)
        if self.scan_errors:
            details = '\n'.join(f'{basename(file)}: {error}' for file, error in self.scan_errors)
            QMessageBox.warning(
                self,
                'Some files failed',
                f'{len(self.scan_errors)} file(s) could not be scanned:\n\n{details}',
            )

    def update_scan_button_state(self):
        regex_ok = self._match_mode() is not MatchMode.REGEX or self._keywords_are_valid_regex()
        self.scan_files.setDisabled(not (self.file_names and self.keyword_list.count() and regex_ok))

    @staticmethod
    def _is_valid_regex(pattern):
        try:
            re.compile(pattern)
        except re.error:
            return False
        return True

    def _keywords_are_valid_regex(self):
        return all(
            self._is_valid_regex(self.keyword_list.item(i).text()) for i in range(self.keyword_list.count())
        )

    def _update_keyword_input_validity(self):
        text = self.new_keyword_text.text()
        invalid = self._match_mode() is MatchMode.REGEX and text and not self._is_valid_regex(text)
        if invalid:
            background = self.options.display.invalid_regex_background.name()
            foreground = self.options.display.invalid_regex_text.name()
            # Set both colors explicitly - a background-only stylesheet left
            # the text color to the OS theme, unreadable against a fixed
            # light background in dark mode.
            self.new_keyword_text.setStyleSheet(f'background-color: {background}; color: {foreground};')
        else:
            self.new_keyword_text.setStyleSheet('')
        self.add_keyword.setDisabled(not text or invalid)

    def _refresh_keyword_validity_highlighting(self):
        regex_mode = self._match_mode() is MatchMode.REGEX
        for i in range(self.keyword_list.count()):
            item = self.keyword_list.item(i)
            invalid = regex_mode and not self._is_valid_regex(item.text())
            if invalid:
                item.setBackground(self.options.display.invalid_regex_background)
                item.setForeground(self.options.display.invalid_regex_text)
            else:
                item.setBackground(QBrush())
                item.setForeground(QBrush())

    def _on_match_mode_changed(self):
        self._refresh_keyword_validity_highlighting()
        self._update_keyword_input_validity()
        self.update_scan_button_state()

    def add_files_clicked(self):
        files = QFileDialog.getOpenFileNames(
            self,
            'Files to Scan',
            self._last_dir(),
            'PDF Documents (*.pdf);;Word Documents (*.docx);;Text (*.txt);;All Files (*)',
        )[0]
        if files:
            self._remember_dir(files[0])
        self._add_files(files)

    def _add_files(self, files):
        if not files:
            return
        count = self.files.rowCount()
        self.files.setRowCount(count + len(files))
        for i, file in enumerate(files):
            self.file_names.append(file)
            self.files.setItem(i + count, 0, QTableWidgetItem(basename(file)))
        self.update_scan_button_state()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile() and isfile(url.toLocalFile())
        ]
        self._add_files(files)

    def remove_files_clicked(self):
        rows = sorted({index.row() for index in self.files.selectedIndexes()}, reverse=True)
        for row in rows:
            del self.file_names[row]
            self.files.removeRow(row)
        self.remove_files.setDisabled(True)
        self.update_scan_button_state()

    def create_keyword_area(self):
        horizontal = QHBoxLayout()
        self.new_keyword_text = QLineEdit()
        self.new_keyword_text.setPlaceholderText('Key word / phrase')
        self.new_keyword_text.textEdited.connect(self._update_keyword_input_validity)
        horizontal.addWidget(self.new_keyword_text)
        self.add_keyword = QPushButton('Add')
        self.add_keyword.setDisabled(True)
        self.add_keyword.clicked.connect(self.add_keyword_clicked)
        horizontal.addWidget(self.add_keyword)
        self.new_keyword_text.returnPressed.connect(self.add_keyword.click)
        vertical = QVBoxLayout()
        vertical.addLayout(horizontal)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('Match mode:'))
        self.match_mode_combo = QComboBox()
        self.match_mode_combo.addItem('Substring', MatchMode.SUBSTRING)
        self.match_mode_combo.addItem('Whole word', MatchMode.WHOLE_WORD)
        self.match_mode_combo.addItem('Regex', MatchMode.REGEX)
        self.match_mode_combo.currentIndexChanged.connect(self._on_match_mode_changed)
        mode_row.addWidget(self.match_mode_combo)
        vertical.addLayout(mode_row)
        self.keyword_list = QListWidget()
        # No in-place editing: an edited keyword wouldn't refresh file headers,
        # save-state, or regex-validity highlighting. Remove + re-add instead.
        self.keyword_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        self.keyword_list.itemSelectionChanged.connect(
            lambda: self.remove_keyword.setDisabled(not self.keyword_list.selectedIndexes())
        )
        vertical.addWidget(self.keyword_list)
        self.remove_keyword = QPushButton('Remove')
        self.remove_keyword.setDisabled(True)
        self.remove_keyword.clicked.connect(self.remove_keyword_clicked)
        vertical.addWidget(self.remove_keyword)
        return vertical

    def add_keyword_clicked(self):
        self.keyword_list.addItem(self.new_keyword_text.text())
        self.new_keyword_text.setText('')
        self._update_keyword_input_validity()
        self.update_file_headers()
        self.save_keywords.setDisabled(False)
        self.update_scan_button_state()
        self.new_keyword_text.setFocus()

    def update_file_headers(self):
        self.file_headers = ['File'] + [self.keyword_list.item(i).text() for i in range(self.keyword_list.count())]
        old_columns = self.files.columnCount()
        len_headers = len(self.file_headers)
        self.files.setColumnCount(len_headers)
        self.files.setHorizontalHeaderLabels(self.file_headers)
        if old_columns < len_headers:
            header = self.files.horizontalHeader()
            for i in range(old_columns, len_headers):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

    def remove_keyword_clicked(self):
        for item in self.keyword_list.selectedIndexes()[::-1]:
            self.keyword_list.takeItem(item.row())
        self.remove_keyword.setDisabled(True)
        self.update_file_headers()
        if not self.keyword_list.count():
            self.save_keywords.setDisabled(True)
        self.update_scan_button_state()
