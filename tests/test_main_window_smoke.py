from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from main_window import FileScanner


def test_window_launches(qtbot):
    window = FileScanner()
    qtbot.addWidget(window)

    assert window.windowTitle() == 'File Scanner'


def test_scan_button_enabled_after_keyword_then_file(qtbot, tmp_path, monkeypatch):
    a_file = str(tmp_path / 'a.txt')
    (tmp_path / 'a.txt').write_text('placeholder')
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', staticmethod(lambda *a, **k: ([a_file], '')))

    window = FileScanner()
    qtbot.addWidget(window)
    assert not window.scan_files.isEnabled()

    window.new_keyword_text.setText('apple')
    window.add_keyword_clicked()
    assert not window.scan_files.isEnabled()

    window.add_files_clicked()
    assert window.scan_files.isEnabled()


def test_scan_button_enabled_after_file_then_keyword(qtbot, tmp_path, monkeypatch):
    a_file = str(tmp_path / 'a.txt')
    (tmp_path / 'a.txt').write_text('placeholder')
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', staticmethod(lambda *a, **k: ([a_file], '')))

    window = FileScanner()
    qtbot.addWidget(window)
    assert not window.scan_files.isEnabled()

    window.add_files_clicked()
    assert not window.scan_files.isEnabled()

    window.new_keyword_text.setText('apple')
    window.add_keyword_clicked()
    assert window.scan_files.isEnabled()


def test_scan_populates_results_and_reports_per_file_errors(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'warning', staticmethod(lambda *a, **k: None))

    good_file = tmp_path / 'good.txt'
    good_file.write_text('this file mentions apple')
    bad_file = tmp_path / 'bad.docx'
    bad_file.write_bytes(b'not a real docx')

    window = FileScanner()
    qtbot.addWidget(window)
    window.keyword_list.addItem('apple')
    window.update_file_headers()
    window.file_names = [str(good_file), str(bad_file)]
    window.files.setRowCount(2)
    window.files.setItem(0, 0, QTableWidgetItem('good.txt'))
    window.files.setItem(1, 0, QTableWidgetItem('bad.docx'))
    window.scan_files.setDisabled(False)

    window.scan_files_clicked()
    qtbot.waitUntil(lambda: not window.scan_worker.isRunning(), timeout=15000)
    qtbot.wait(50)

    assert window.files.item(0, 1).text() == 'true'
    assert window.files.item(1, 1).text() == 'ERROR'
    assert len(window.scan_errors) == 1
    assert window.export_results.isEnabled()
    assert window.scan_files.isEnabled()
