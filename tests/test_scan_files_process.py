from scanner import MAX_OCCURRENCES_PER_KEYWORD, MatchMode, scan_files_process


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


def test_whole_word_mode_avoids_substring_false_positive(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('concatenate this')

    result = scan_files_process(['cat'], str(path), mode=MatchMode.WHOLE_WORD)

    assert result.error is None
    assert result.matches == [False]


def test_whole_word_mode_matches_standalone_word(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('the cat sat')

    result = scan_files_process(['cat'], str(path), mode=MatchMode.WHOLE_WORD)

    assert result.error is None
    assert result.matches == [True]


def test_regex_mode_matches_pattern(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('invoice #12345 due')

    result = scan_files_process([r'#\d+'], str(path), mode=MatchMode.REGEX)

    assert result.error is None
    assert result.matches == [True]


def test_regex_mode_reports_error_for_invalid_pattern(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('hello')

    result = scan_files_process(['('], str(path), mode=MatchMode.REGEX)

    assert result.matches is None
    assert result.error is not None


def test_substring_mode_matches_phrase_split_by_line_wrap(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('grape\njuice is tasty')

    result = scan_files_process(['grape juice'], str(path))

    assert result.error is None
    assert result.matches == [True]


def test_whole_word_mode_matches_phrase_split_by_line_wrap(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('the grape\njuice is tasty')

    result = scan_files_process(['grape juice'], str(path), mode=MatchMode.WHOLE_WORD)

    assert result.error is None
    assert result.matches == [True]


def test_regex_mode_does_not_collapse_whitespace(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('grape\njuice')

    # A literal space in the pattern must not match the newline - regex mode
    # intentionally sees the raw extracted text, unlike substring/whole-word.
    result = scan_files_process(['grape juice'], str(path), mode=MatchMode.REGEX)

    assert result.error is None
    assert result.matches == [False]


def test_all_occurrences_reported_not_just_first(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('apple one, apple two, apple three')

    result = scan_files_process(['apple'], str(path))

    assert len(result.occurrences[0]) == 3
    assert result.truncated == [False]


def test_occurrence_count_capped_and_truncated_flag_set(tmp_path):
    path = tmp_path / 'notes.txt'
    path.write_text('apple ' * (MAX_OCCURRENCES_PER_KEYWORD + 5))

    result = scan_files_process(['apple'], str(path))

    assert len(result.occurrences[0]) == MAX_OCCURRENCES_PER_KEYWORD
    assert result.truncated == [True]


def test_pdf_page_number_reported_for_each_occurrence(multipage_pdf_file):
    result = scan_files_process(['apple'], multipage_pdf_file)

    assert result.error is None
    pages = [occ.page for occ in result.occurrences[0]]
    assert pages == [1, 2]


def test_pdf_single_page_reports_page_one(pdf_file):
    result = scan_files_process(['apple'], pdf_file)

    assert [occ.page for occ in result.occurrences[0]] == [1]


def test_docx_and_txt_have_no_page_number(docx_file, tmp_path):
    txt_path = tmp_path / 'notes.txt'
    txt_path.write_text('banana bread recipe')

    docx_result = scan_files_process(['banana'], docx_file)
    txt_result = scan_files_process(['banana'], str(txt_path))

    assert [occ.page for occ in docx_result.occurrences[0]] == [None]
    assert [occ.page for occ in txt_result.occurrences[0]] == [None]


def test_phrase_split_across_pdf_page_break_still_matches(split_phrase_pdf_file):
    result = scan_files_process(['grape juice'], split_phrase_pdf_file)

    assert result.error is None
    assert result.matches == [True]
    assert len(result.occurrences[0]) == 1


def test_disambiguate_labels_keeps_unique_names_bare():
    from scanner import disambiguate_labels

    labels = disambiguate_labels(['/home/a/report.pdf', '/home/b/notes.txt'])

    assert labels == {'/home/a/report.pdf': 'report.pdf', '/home/b/notes.txt': 'notes.txt'}


def test_disambiguate_labels_adds_minimal_path_fragment_on_collision():
    from scanner import disambiguate_labels

    labels = disambiguate_labels(['/data/2023/report.pdf', '/data/2024/report.pdf', '/other/notes.txt'])

    assert labels['/data/2023/report.pdf'] == '…/2023/report.pdf'
    assert labels['/data/2024/report.pdf'] == '…/2024/report.pdf'
    assert labels['/other/notes.txt'] == 'notes.txt'


def test_disambiguate_labels_walks_further_up_when_needed():
    from scanner import disambiguate_labels

    labels = disambiguate_labels(['/a/q1/data/report.pdf', '/b/q1/data/report.pdf'])

    assert labels['/a/q1/data/report.pdf'] == '…/a/q1/data/report.pdf'
    assert labels['/b/q1/data/report.pdf'] == '…/b/q1/data/report.pdf'
