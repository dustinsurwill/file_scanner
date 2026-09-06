import sys
from _csv import writer
from functools import partial
from multiprocessing import cpu_count, get_context
from os.path import basename

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
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
from scanner import ScanResult, scan_files_process

# Recycle each worker after this many files so any per-file memory that a
# parsing library doesn't fully release (observed with pdfminer.six on large
# PDF batches) can't accumulate across the life of a long-running scan.
MAX_TASKS_PER_CHILD = 50
ERROR_CELL_COLOR = QColor('orange')


class ScanWorker(QThread):
    result_ready = pyqtSignal(object)
    finished_scanning = pyqtSignal()

    def __init__(self, keywords, file_names, parent=None):
        super().__init__(parent)
        self.keywords = keywords
        self.file_names = file_names

    def run(self):
        worker_count = min(cpu_count(), len(self.file_names))
        scan = partial(scan_files_process, self.keywords)
        # 'spawn' (not the platform-default 'fork' on Linux) avoids worker
        # processes inheriting this QThread's/QApplication's state, which
        # otherwise deadlocks pool shutdown when a Pool is created from a
        # non-main thread in a Qt app.
        context = get_context('spawn')
        with context.Pool(processes=worker_count, maxtasksperchild=MAX_TASKS_PER_CHILD) as pool:
            for result in pool.imap_unordered(scan, self.file_names):
                self.result_ready.emit(result)
        self.finished_scanning.emit()


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
        if sys.platform == 'win32':
            QApplication.setStyle(QStyleFactory.create('windowsvista'))
        self.file_names = []
        self.file_rows = {}
        self.scan_errors = []
        self.options = Options(self)
        self.scan_worker = None
        self.progress_dialog = None

    def create_files_area(self):
        vertical = QVBoxLayout()
        top_buttons = QHBoxLayout()
        self.add_files = QPushButton('Add Files')
        self.add_files.clicked.connect(self.add_files_clicked)
        top_buttons.addWidget(self.add_files)
        self.export_results = QPushButton('Export Results')
        self.export_results.setDisabled(True)
        self.export_results.clicked.connect(self.export_results_clicked)
        top_buttons.addWidget(self.export_results)
        vertical.addLayout(top_buttons)
        self.files = QTableWidget()
        self.files.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.files.setAlternatingRowColors(True)
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
        target_path = QFileDialog.getSaveFileName(self, 'Export Results', '.', 'Excel (*.csv)')[0]
        if not target_path:
            return
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

    def save_keywords_clicked(self):
        target_path = QFileDialog.getSaveFileName(self, 'Save Keywords', '.', 'Text (*.txt)')[0]
        if not target_path:
            return
        keywords = [self.keyword_list.item(i).text() for i in range(self.keyword_list.count())]
        try:
            with open(target_path, 'wt') as keywords_file:
                keywords_file.write('\n'.join(keywords) + '\n')
        except OSError as exc:
            QMessageBox.critical(self, 'Save Failed', f'Could not save keywords:\n{exc}')

    def load_keywords_clicked(self):
        source_path = QFileDialog.getOpenFileName(self, 'Load Keywords', '.', 'Text (*.txt)')[0]
        if not source_path:
            return
        try:
            with open(source_path, 'rt') as keywords_file:
                loaded_keywords = [line for line in keywords_file.read().split('\n') if line]
        except OSError as exc:
            QMessageBox.critical(self, 'Load Failed', f'Could not load keywords:\n{exc}')
            return
        self.keyword_list.addItems(loaded_keywords)
        self.update_file_headers()
        if self.keyword_list.count():
            self.save_keywords.setDisabled(False)
        self.update_scan_button_state()

    def scan_files_clicked(self):
        if not self.file_names:
            return
        keywords = [self.keyword_list.item(i).text().lower() for i in range(self.keyword_list.count())]
        self.file_rows = {file: row for row, file in enumerate(self.file_names)}
        self.scan_errors = []
        self.scan_files.setDisabled(True)
        self.add_files.setDisabled(True)
        self.progress_dialog = QProgressDialog('Scanning files...', None, 0, len(self.file_names), self)
        self.progress_dialog.setWindowTitle('Scanning')
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.scan_worker = ScanWorker(keywords, list(self.file_names), self)
        self.scan_worker.result_ready.connect(self.handle_scan_result)
        self.scan_worker.finished_scanning.connect(self.handle_scan_finished)
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
        if self.scan_errors:
            details = '\n'.join(f'{basename(file)}: {error}' for file, error in self.scan_errors)
            QMessageBox.warning(
                self,
                'Some files failed',
                f'{len(self.scan_errors)} file(s) could not be scanned:\n\n{details}',
            )

    def update_scan_button_state(self):
        self.scan_files.setDisabled(not (self.file_names and self.keyword_list.count()))

    def add_files_clicked(self):
        files = QFileDialog.getOpenFileNames(
            self, 'Files to Scan', '.', 'PDF Documents (*.pdf);;Word Documents (*.docx);;Text (*.txt);;All Files (*)'
        )[0]
        if files:
            count = self.files.rowCount()
            self.files.setRowCount(count + len(files))
            for i, file in enumerate(files):
                self.file_names.append(file)
                self.files.setItem(i + count, 0, QTableWidgetItem(basename(file)))
            self.update_scan_button_state()

    def create_keyword_area(self):
        horizontal = QHBoxLayout()
        self.new_keyword_text = QLineEdit()
        self.new_keyword_text.setPlaceholderText('Key word / phrase')
        self.new_keyword_text.textEdited.connect(lambda: self.add_keyword.setDisabled(not self.new_keyword_text.text()))
        horizontal.addWidget(self.new_keyword_text)
        self.add_keyword = QPushButton('Add')
        self.add_keyword.setDisabled(True)
        self.add_keyword.clicked.connect(self.add_keyword_clicked)
        horizontal.addWidget(self.add_keyword)
        self.new_keyword_text.returnPressed.connect(self.add_keyword.click)
        vertical = QVBoxLayout()
        vertical.addLayout(horizontal)
        self.keyword_list = QListWidget()
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
        self.add_keyword.setDisabled(True)
        self.new_keyword_text.setText('')
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
