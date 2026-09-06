import zipfile

import pytest
from PyQt6.QtCore import QSettings
from reportlab.pdfgen import canvas

import main_window


@pytest.fixture(autouse=True)
def isolated_qsettings(tmp_path, monkeypatch):
    ini_path = str(tmp_path / 'settings.ini')
    monkeypatch.setattr(
        main_window, 'QSettings', lambda *a, **k: QSettings(ini_path, QSettings.Format.IniFormat)
    )


def make_pdf(path, text):
    page = canvas.Canvas(path)
    page.drawString(72, 720, text)
    page.save()


def make_multipage_pdf(path, texts):
    page = canvas.Canvas(path)
    for text in texts:
        page.drawString(72, 720, text)
        page.showPage()
    page.save()


def make_docx(path, text):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(
            '[Content_Types].xml',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>',
        )
        archive.writestr(
            '_rels/.rels',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            '</Relationships>',
        )
        archive.writestr(
            'word/document.xml',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>',
        )


@pytest.fixture
def pdf_file(tmp_path):
    path = tmp_path / 'sample.pdf'
    make_pdf(str(path), 'apple pie recipe')
    return str(path)


@pytest.fixture
def docx_file(tmp_path):
    path = tmp_path / 'sample.docx'
    make_docx(str(path), 'banana bread recipe')
    return str(path)


@pytest.fixture
def multipage_pdf_file(tmp_path):
    path = tmp_path / 'multipage.pdf'
    make_multipage_pdf(str(path), ['apple on page one', 'apple on page two also', 'nothing relevant here'])
    return str(path)


@pytest.fixture
def split_phrase_pdf_file(tmp_path):
    # "grape juice" spans the page break: page 1 ends with "grape", page 2
    # starts with "juice", with no separator pypdfium2 would supply itself.
    path = tmp_path / 'split.pdf'
    make_multipage_pdf(str(path), ['this ends with grape', 'juice starts the next page'])
    return str(path)
