from PyQt6.QtWidgets import QFileDialog

from main_window import FileScanner


def test_save_then_load_round_trips_multiple_keywords(qtbot, tmp_path, monkeypatch):
    keywords_path = str(tmp_path / 'keywords.txt')

    writer = FileScanner()
    qtbot.addWidget(writer)
    for keyword in ['apple', 'grape juice', 'cherry']:
        writer.keyword_list.addItem(keyword)

    monkeypatch.setattr(QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: (keywords_path, '')))
    writer.save_keywords_clicked()

    reader = FileScanner()
    qtbot.addWidget(reader)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: (keywords_path, '')))
    reader.load_keywords_clicked()

    loaded = [reader.keyword_list.item(i).text() for i in range(reader.keyword_list.count())]
    assert loaded == ['apple', 'grape juice', 'cherry']
