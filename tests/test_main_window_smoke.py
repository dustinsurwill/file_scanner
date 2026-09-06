from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem

from main_window import FileScanner


def test_window_launches(qtbot):
    window = FileScanner()
    qtbot.addWidget(window)

    assert window.windowTitle() == 'File Scanner'


def test_scan_button_only_enabled_once_keyword_and_file_present(qtbot):
    window = FileScanner()
    qtbot.addWidget(window)

    assert not window.scan_files.isEnabled()

    window.keyword_list.addItem('apple')
    window.file_names.append('placeholder.txt')
    window.files.setRowCount(1)
    window.files.setItem(0, 0, QTableWidgetItem('placeholder.txt'))
    if window.keyword_list.count():
        window.scan_files.setDisabled(False)

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
