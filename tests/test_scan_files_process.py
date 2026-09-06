from scanner import scan_files_process


def test_matches_keywords_in_txt_file(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('This file mentions apple and banana.')

    result = scan_files_process(['apple', 'grape'], str(path))

    assert result.error is None
    assert result.matches == [True, False]


def test_matches_are_case_insensitive(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('APPLE PIE')

    result = scan_files_process(['apple'], str(path))

    assert result.matches == [True]


def test_extension_detection_is_case_insensitive(pdf_file, tmp_path):
    upper_path = tmp_path / 'SAMPLE.PDF'
    upper_path.write_bytes((tmp_path / 'sample.pdf').read_bytes())

    result = scan_files_process(['apple'], str(upper_path))

    assert result.error is None
    assert result.matches == [True]


def test_scans_pdf(pdf_file):
    result = scan_files_process(['apple', 'cherry'], pdf_file)

    assert result.error is None
    assert result.matches == [True, False]


def test_scans_docx(docx_file):
    result = scan_files_process(['banana', 'cherry'], docx_file)

    assert result.error is None
    assert result.matches == [True, False]


def test_corrupt_file_reports_error_instead_of_raising(tmp_path):
    path = tmp_path / 'corrupt.docx'
    path.write_bytes(b'not actually a docx file')

    result = scan_files_process(['apple'], str(path))

    assert result.matches is None
    assert result.error is not None


def test_missing_file_reports_error_instead_of_raising(tmp_path):
    missing_path = tmp_path / 'does_not_exist.pdf'

    result = scan_files_process(['apple'], str(missing_path))

    assert result.matches is None
    assert result.error is not None


def test_non_utf8_text_file_reports_matches_instead_of_raising(tmp_path):
    path = tmp_path / 'latin1.txt'
    path.write_bytes('café apple'.encode('latin-1'))

    result = scan_files_process(['apple'], str(path))

    assert result.error is None
    assert result.matches == [True]
