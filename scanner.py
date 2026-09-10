import re
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import docx2txt
import pypdfium2

# Tooltip safety net: an unbounded keyword match (a common word, or a
# pathological regex) must not make one file's scan blow up processing time
# or tooltip size.
MAX_OCCURRENCES_PER_KEYWORD = 20


class MatchMode(Enum):
    SUBSTRING = 'substring'
    WHOLE_WORD = 'whole_word'
    REGEX = 'regex'


@dataclass
class Occurrence:
    page: int | None
    snippet: str


@dataclass
class ScanResult:
    file: str
    matches: list[bool] | None = None
    occurrences: list[list[Occurrence]] | None = None
    truncated: list[bool] | None = None
    error: str | None = None


def disambiguate_labels(paths: list[str]) -> dict[str, str]:
    """Map each path to a display label. A path whose file name is unique in the
    list gets just that name; paths that share a file name get the shortest
    trailing fragment of their path that tells them apart (prefixed with '…/'
    when it isn't the whole path), e.g. '…/2023/report.pdf' vs '…/2024/report.pdf'.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        groups[Path(path).name].append(path)
    labels: dict[str, str] = {}
    for name, group in groups.items():
        if len(group) == 1:
            labels[group[0]] = name
            continue
        parts_by_path = {path: Path(path).parts for path in group}
        for path, parts in parts_by_path.items():
            label = path  # fallback for genuinely identical paths (e.g. added twice)
            for depth in range(2, len(parts) + 1):
                tail = parts[-depth:]
                if sum(1 for other in parts_by_path.values() if other[-depth:] == tail) == 1:
                    joined = '/'.join(tail)
                    label = joined if depth == len(parts) else f'…/{joined}'
                    break
            labels[path] = label
    return labels


def extract_text(file: str) -> tuple[str, list[int] | None]:
    """Returns (text, page_boundaries). page_boundaries[i] is the offset in `text`
    where page i+1 ends (1-based page numbers) - only set for .pdf, which is the
    only one of these formats with a stored page concept. .docx pagination is a
    print-time layout computation, not stored in the file; .txt has no pages."""
    suffix = Path(file).suffix.lower()
    if suffix == '.pdf':
        chunks = []
        boundaries = []
        offset = 0
        with pypdfium2.PdfDocument(file) as document:
            for page in document:
                textpage = page.get_textpage()
                page_text = textpage.get_text_range()
                textpage.close()
                page.close()
                if chunks:
                    # Guarantee a word boundary at the page break - pypdfium2
                    # won't have inserted one, and without it the last word of
                    # one page could fuse with the first word of the next.
                    chunks.append(' ')
                    offset += 1
                chunks.append(page_text)
                offset += len(page_text)
                boundaries.append(offset)
        return ''.join(chunks), boundaries
    if suffix == '.docx':
        return docx2txt.process(file), None
    with open(file, 'rt', encoding='utf-8', errors='replace') as text_file:
        return text_file.read(), None


def _collapse_whitespace(value: str) -> str:
    return re.sub(r'\s+', ' ', value.strip())


def _collapse_with_mapping(text: str) -> tuple[str, list[int]]:
    """Like _collapse_whitespace, but also returns index_map where index_map[i] is
    the offset in the original `text` that produced collapsed-text character i -
    needed to trace a match found in the collapsed text back to a page number."""
    out_chars = []
    index_map = []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            out_chars.append(' ')
            index_map.append(i)
            while i < n and text[i].isspace():
                i += 1
        else:
            out_chars.append(text[i])
            index_map.append(i)
            i += 1
    return ''.join(out_chars), index_map


def _page_for_offset(page_boundaries: list[int] | None, offset: int) -> int | None:
    if page_boundaries is None:
        return None
    return bisect_right(page_boundaries, offset) + 1


def _snippet(text: str, start: int, end: int, radius: int = 30) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    prefix = '…' if lo > 0 else ''
    suffix = '…' if hi < len(text) else ''
    return f'{prefix}{text[lo:hi].strip()}{suffix}'


def _all_occurrences(
    keyword: str,
    mode: MatchMode,
    text: str,
    index_map: list[int] | None,
    page_boundaries: list[int] | None,
) -> tuple[list[Occurrence], bool]:
    """Returns (occurrences, truncated). `text` is the collapsed document for
    SUBSTRING/WHOLE_WORD, or the raw document for REGEX (which intentionally
    skips whitespace collapsing - see scan_files_process). `index_map` translates
    a position in collapsed `text` back to raw-text offset for page lookup; it's
    None for REGEX, where `text` offsets are already raw."""
    occurrences = []
    truncated = False

    def add(start: int, end: int) -> bool:
        """Returns False once the cap is hit (caller should stop iterating)."""
        nonlocal truncated
        if len(occurrences) >= MAX_OCCURRENCES_PER_KEYWORD:
            truncated = True
            return False
        raw_offset = index_map[start] if index_map is not None else start
        page = _page_for_offset(page_boundaries, raw_offset)
        occurrences.append(Occurrence(page=page, snippet=_snippet(text, start, end)))
        return True

    if mode is MatchMode.SUBSTRING:
        keyword = _collapse_whitespace(keyword)
        if not keyword:
            return occurrences, truncated
        start = 0
        while True:
            pos = text.find(keyword, start)
            if pos == -1:
                break
            if not add(pos, pos + len(keyword)):
                break
            start = pos + len(keyword)
    else:
        pattern = rf'\b{re.escape(_collapse_whitespace(keyword))}\b' if mode is MatchMode.WHOLE_WORD else keyword
        for match in re.finditer(pattern, text):
            if not add(match.start(), match.end()):
                break

    return occurrences, truncated


def scan_files_process(keywords: list[str], file: str, mode: MatchMode = MatchMode.SUBSTRING) -> ScanResult:
    try:
        raw_text, page_boundaries = extract_text(file)
    except Exception as exc:  # noqa: BLE001 - any parser failure becomes a per-file error, not a crash
        return ScanResult(file=file, error=str(exc))
    raw_text = raw_text.lower()
    if mode is MatchMode.REGEX:
        # Regex mode is the power-user escape hatch and should see the real
        # text - no whitespace collapsing, so no index_map needed.
        search_text, index_map = raw_text, None
    else:
        # A line-wrapped PDF/DOCX paragraph can turn the space in a multi-word
        # keyword into a newline in the extracted text; collapse whitespace
        # runs so that still counts as a match.
        search_text, index_map = _collapse_with_mapping(raw_text)
    try:
        matches = []
        occurrences = []
        truncated = []
        for keyword in keywords:
            keyword_occurrences, keyword_truncated = _all_occurrences(
                keyword, mode, search_text, index_map, page_boundaries
            )
            matches.append(bool(keyword_occurrences))
            occurrences.append(keyword_occurrences)
            truncated.append(keyword_truncated)
        return ScanResult(file=file, matches=matches, occurrences=occurrences, truncated=truncated)
    except re.error as exc:  # regex mode with a pattern that slipped past UI validation
        return ScanResult(file=file, error=f'Invalid regex pattern: {exc}')
