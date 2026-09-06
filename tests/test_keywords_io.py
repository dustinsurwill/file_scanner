from PyQt6.QtWidgets import QFileDialog

from main_window import FileScanner
from scanner import MatchMode


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


def test_save_keywords_appends_missing_extension(qtbot, tmp_path, monkeypatch):
    typed_path = str(tmp_path / 'keywords')  # no extension typed
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: (typed_path, '')))

    window = FileScanner()
    qtbot.addWidget(window)
    window.keyword_list.addItem('apple')

    window.save_keywords_clicked()

    with open(typed_path + '.txt') as saved:
        assert 'apple' in saved.read()


def test_match_mode_round_trips_through_saved_keyword_file(qtbot, tmp_path, monkeypatch):
    keywords_path = str(tmp_path / 'keywords.txt')

    writer = FileScanner()
    qtbot.addWidget(writer)
    writer.keyword_list.addItem(r'\d{4,}')
    writer.match_mode_combo.setCurrentIndex(writer.match_mode_combo.findData(MatchMode.REGEX))
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: (keywords_path, '')))
    writer.save_keywords_clicked()

    reader = FileScanner()
    qtbot.addWidget(reader)
    assert reader._match_mode() is MatchMode.SUBSTRING  # default, before loading
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: (keywords_path, '')))
    reader.load_keywords_clicked()

    assert reader._match_mode() is MatchMode.REGEX
    loaded = [reader.keyword_list.item(i).text() for i in range(reader.keyword_list.count())]
    assert loaded == [r'\d{4,}']  # the mode marker line must not show up as a keyword


def test_loading_plain_keyword_file_without_marker_leaves_current_mode(qtbot, tmp_path, monkeypatch):
    keywords_path = tmp_path / 'plain.txt'
    keywords_path.write_text('apple\nbanana\n')  # hand-written, no mode marker

    window = FileScanner()
    qtbot.addWidget(window)
    window.match_mode_combo.setCurrentIndex(window.match_mode_combo.findData(MatchMode.WHOLE_WORD))
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', staticmethod(lambda *a, **k: (str(keywords_path), '')))

    window.load_keywords_clicked()

    assert window._match_mode() is MatchMode.WHOLE_WORD
    loaded = [window.keyword_list.item(i).text() for i in range(window.keyword_list.count())]
    assert loaded == ['apple', 'banana']


def test_match_mode_persists_across_instances(qtbot):
    window = FileScanner()
    qtbot.addWidget(window)
    window.match_mode_combo.setCurrentIndex(window.match_mode_combo.findData(MatchMode.REGEX))
    window.close()

    reopened = FileScanner()
    qtbot.addWidget(reopened)

    assert reopened._match_mode() is MatchMode.REGEX
