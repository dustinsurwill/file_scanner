from dataclasses import dataclass
from pathlib import Path

import docx2txt
import pypdfium2


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


def scan_files_process(keywords: list[str], file: str) -> ScanResult:
    try:
        text = extract_text(file).lower()
    except Exception as exc:  # noqa: BLE001 - any parser failure becomes a per-file error, not a crash
        return ScanResult(file=file, error=str(exc))
    return ScanResult(file=file, matches=[keyword in text for keyword in keywords])
