import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import docx2txt
import pypdfium2


class MatchMode(Enum):
    SUBSTRING = 'substring'
    WHOLE_WORD = 'whole_word'
    REGEX = 'regex'


@dataclass
class ScanResult:
    file: str
    matches: list[bool] | None = None
    error: str | None = None


def extract_text(file: str) -> str:
    suffix = Path(file).suffix.lower()
    if suffix == '.pdf':
        text = ''
        with pypdfium2.PdfDocument(file) as document:
            for page in document:
                textpage = page.get_textpage()
                text += textpage.get_text_range()
                textpage.close()
                page.close()
        return text
    if suffix == '.docx':
        return docx2txt.process(file)
    with open(file, 'rt', encoding='utf-8', errors='replace') as text_file:
        return text_file.read()


def _collapse_whitespace(value: str) -> str:
    return re.sub(r'\s+', ' ', value.strip())


def _keyword_matches(keyword: str, mode: MatchMode, text: str) -> bool:
    if mode is MatchMode.SUBSTRING:
        return _collapse_whitespace(keyword) in text
    if mode is MatchMode.WHOLE_WORD:
        return re.search(rf'\b{re.escape(_collapse_whitespace(keyword))}\b', text) is not None
    return re.search(keyword, text) is not None  # MatchMode.REGEX - operates on raw, uncollapsed text


def scan_files_process(keywords: list[str], file: str, mode: MatchMode = MatchMode.SUBSTRING) -> ScanResult:
    try:
        text = extract_text(file).lower()
    except Exception as exc:  # noqa: BLE001 - any parser failure becomes a per-file error, not a crash
        return ScanResult(file=file, error=str(exc))
    if mode is not MatchMode.REGEX:
        # A line-wrapped PDF/DOCX paragraph can turn the space in a multi-word
        # keyword into a newline in the extracted text; collapse whitespace
        # runs so that still counts as a match. Regex mode is left alone -
        # it's the power-user escape hatch and should see the real text.
        text = _collapse_whitespace(text)
    try:
        return ScanResult(file=file, matches=[_keyword_matches(keyword, mode, text) for keyword in keywords])
    except re.error as exc:  # regex mode with a pattern that slipped past UI validation
        return ScanResult(file=file, error=f'Invalid regex pattern: {exc}')
