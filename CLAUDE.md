# CLAUDE.md

Guidance for working in this repo.

## Commands
- Install deps: `uv sync --group test`
- Run app: `uv run python main.py`
- Run tests: `QT_QPA_PLATFORM=offscreen uv run --frozen --group test pytest -v`
- Lint: `uv run --frozen --group lint ruff check .`
- Build Windows exe: `uv run --group build nuitka main.py`

Always use `uv run`/`uv sync`; don't invoke `python`/`pip` directly. Use `--frozen` for
tests/lint/build so `uv.lock` isn't silently regenerated — regenerate it deliberately
(`uv sync`) when `pyproject.toml` changes, and commit the lockfile alongside that change.

## Architecture
- `scanner.py` holds the pure scan/extraction logic (`ScanResult`, `scan_files_process`) — no Qt
  imports, so it's directly unit-testable and pickle-friendly for `multiprocessing`.
- `main_window.py` holds `ScanWorker` (a `QThread` driving a `multiprocessing.Pool`) and
  `FileScanner` (the main window).
- `main.py` is trimmed to the entry point plus `# nuitka-project:` build-flag comments.

## Non-obvious constraints
- `ScanWorker` must use `multiprocessing.get_context('spawn')`, not the Linux-default `fork`
  context. Creating a fork-based `Pool` from a `QThread` inside a Qt app deadlocks pool shutdown.
- `maxtasksperchild=MAX_TASKS_PER_CHILD` in `ScanWorker.run()` recycles workers periodically —
  this is a deliberate guard against per-file memory that PDF-parsing libraries don't fully
  release, which is what caused the original crash on large batches (~9000 PDFs).
- `FileScanner.__init__` must never call `self.show()` — that previously crashed CI on
  `windows-latest` (`QPaintDevice: Cannot destroy paint device that is being painted`). Call
  `.show()` from `main.py` after construction instead.
- `main.py` needs `multiprocessing.freeze_support()` as the first line in `__main__` — required
  for `Pool` to work in the Nuitka-frozen Windows executable.
- Any code path that mutates `file_names` or the keyword list must call
  `update_scan_button_state()` — there is no other single source of truth for whether the Scan
  button should be enabled (this was a real, previously-shipped bug).

## Tests
- `tests/conftest.py` has an autouse `isolated_qsettings` fixture that monkeypatches
  `main_window.QSettings` to a per-test temp ini file. Never remove this — without it, tests
  read/write the developer's real `~/.config/file-scanner/FileScanner.conf` (this happened once;
  `QSettings.setPath()` does *not* reliably isolate PyQt6's `QSettings(org, app)` constructor).
- `QUrl.toLocalFile()` returns forward-slash paths on Windows even though `str(Path(...))` uses
  backslashes — normalize with `os.path.normpath` before comparing paths in tests (see
  `test_drag_and_drop_adds_files`).
- GUI tests run headless via `QT_QPA_PLATFORM=offscreen`; CI installs a handful of system Qt
  libraries on `ubuntu-latest` for this (`libglib2.0-0 libegl1 libgl1 libfontconfig1
  libxkbcommon0 libdbus-1-3` — see `.github/workflows/test.yml`).

## Versioning
Version is derived from git tags via `setuptools-scm` (see `[tool.setuptools_scm]` in
`pyproject.toml`) — never hand-edit a version number in the code.

## Backlog (deliberately deferred, not TODOs to pick up unprompted)
Session save/load, `.xlsx` export, whole-word/regex keyword matching, result snippets/context,
sortable/filterable results table, persisted window geometry, dark-mode consistency on Linux,
double-click a row to open the file.
