from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import docx2txt
import pymupdf


@dataclass
class ScanResult:
    file: str
    matches: Optional[List[bool]] = None
    error: Optional[str] = None


def extract_text(file: str) -> str:
    suffix = Path(file).suffix.lower()
    if suffix == '.pdf':
        with pymupdf.open(file) as document:
            return ''.join(page.get_text() for page in document)
    if suffix == '.docx':
        return docx2txt.process(file)
    with open(file, 'rt', encoding='utf-8', errors='replace') as text_file:
        return text_file.read()


def scan_files_process(keywords: List[str], file: str) -> ScanResult:
    try:
        text = extract_text(file).lower()
    except Exception as exc:
        return ScanResult(file=file, error=str(exc))
    return ScanResult(file=file, matches=[keyword in text for keyword in keywords])
