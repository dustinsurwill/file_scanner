import zipfile

import pymupdf
import pytest
from PyQt6.QtCore import QSettings

import main_window


@pytest.fixture(autouse=True)
def isolated_qsettings(tmp_path, monkeypatch):
    ini_path = str(tmp_path / 'settings.ini')
    monkeypatch.setattr(
        main_window, 'QSettings', lambda *a, **k: QSettings(ini_path, QSettings.Format.IniFormat)
    )


def make_pdf(path, text):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


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
