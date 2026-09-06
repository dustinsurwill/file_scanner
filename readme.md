# File Scanner

A small PyQt6 desktop app for scanning a batch of files (`.pdf`, `.docx`, `.txt`) for a set of
keywords, showing a found/missing grid you can export to CSV.

## Features
- Add files via a file picker or by dragging them onto the window
- Remove selected files from the batch without starting over
- Add/remove/save/load keyword lists
- Scan runs on a background process pool so the UI stays responsive, with a progress dialog you
  can cancel mid-scan
- Per-file scan errors (corrupt/unreadable files) are reported without failing the whole batch
- Export results to CSV
- Remembers the last-used directory across file dialogs

## Requirements
- Python 3.14+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup
```bash
uv sync --group test
```

## Running
```bash
uv run python main.py
```

## Testing
```bash
QT_QPA_PLATFORM=offscreen uv run --frozen --group test pytest -v
```
(`QT_QPA_PLATFORM=offscreen` isn't needed if you have a display available.)

## Linting
```bash
uv run --frozen --group lint ruff check .
```

## Building a Windows executable
```bash
uv run --group build nuitka main.py
```
Build flags live as `# nuitka-project:` comments at the top of `main.py`, including
`--low-memory`, `--lto=no`, and `--include-qt-plugins=platforms` — these keep the C-compilation
step's memory use bounded (see CLAUDE.md for why). A GitHub Actions workflow
(`.github/workflows/build-exe.yml`) also builds and attaches the `.exe` to GitHub Releases when a
`v*` tag is pushed.

## Project layout
- `main.py` — entry point, Nuitka build flags
- `main_window.py` — main window UI and the background `ScanWorker`
- `scanner.py` — pure scan/extraction logic (no Qt dependency), used by the worker pool
- `options_dialog.py` — display options (colors/labels for found/missing)
- `tests/` — pytest + pytest-qt test suite
