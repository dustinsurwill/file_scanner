# File Scanner

A small PyQt6 desktop app for scanning a batch of files (`.pdf`, `.docx`, `.txt`) for a set of
keywords, showing a found/missing grid you can export to CSV.

## Features
- Add files via a file picker or by dragging them onto the window
- Remove selected files from the batch without starting over
- Add/remove/save/load keyword lists
- Match keywords as a substring, whole word, or regex pattern, with invalid regex patterns
  flagged live and blocked from starting a scan
- Scan runs on a background process pool so the UI stays responsive, with a progress dialog you
  can cancel mid-scan
- Per-file scan errors (corrupt/unreadable files) are reported without failing the whole batch
- Hover a found cell to see every match as a snippet of surrounding text (with a PDF page number,
  where the format supports one)
- Sort results by clicking a column header, or filter rows by typing in the filter box
- Double-click a row to open that file in its default app
- Export results to CSV or a color-coded `.xlsx` workbook
- Customizable found/missing/scan-error colors and labels (Options dialog), persisted across runs
- Remembers the last-used directory across file dialogs and the window's size/position across runs
- Has an actual app/taskbar icon instead of the default Qt one

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

## Building a standalone executable
```bash
uv run --group build nuitka main.py
```
Produces `file-scanner.exe` on Windows or `file-scanner` on Linux. Build flags live as
`# nuitka-project:` comments at the top of `main.py`, including `--low-memory`, `--lto=no`, and
`--include-qt-plugins=platforms` — these keep the C-compilation step's memory use bounded (see
CLAUDE.md for why). A GitHub Actions workflow (`.github/workflows/build-exe.yml`) also builds
both platforms and attaches the binaries to GitHub Releases when a `v*` tag is pushed.

## Project layout
- `main.py` — entry point, Nuitka build flags
- `main_window.py` — main window UI and the background `ScanWorker`
- `scanner.py` — pure scan/extraction logic (no Qt dependency), used by the worker pool
- `options_dialog.py` — display options (colors/labels for found/missing/scan-error)
- `assets/` — app icon (`icon.svg` source, `icon.png` for the runtime window icon, `icon.ico` for
  the Windows executable resource)
- `tests/` — pytest + pytest-qt test suite
