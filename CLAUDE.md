# CLAUDE.md

Guidance for working in this repo.

## Commands
- Install deps: `uv sync --group test`
- Run app: `uv run python main.py`
- Run tests: `QT_QPA_PLATFORM=offscreen uv run --frozen --group test pytest -v`
- Lint: `uv run --frozen --group lint ruff check .`
- Build standalone exe: `uv run --group build nuitka main.py` (produces `file-scanner.exe` on
  Windows, `file-scanner` on Linux)

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
  for `Pool` to work in the Nuitka-frozen Windows executable. Verified working: a frozen
  `--onefile` binary running a `QThread` that drives a `spawn`-context `Pool.imap_unordered` (the
  exact `ScanWorker` pattern) completes correctly with no deadlock — tested directly against a
  compiled binary, not just inferred from docs.
- PDF extraction uses `pypdfium2`, not `PyMuPDF`/`fitz` — **do not switch back to PyMuPDF**.
  PyMuPDF's `mupdf.py` is a multi-megabyte SWIG-generated wrapper; Nuitka compiles every followed
  pure-Python module to C, and that specific file reliably OOMs the C backend compiler (`cc1`)
  even at 80GB+ RAM. This is a confirmed, unresolved upstream bug affecting both `--onefile` and
  `--standalone` (see [Nuitka#3243](https://github.com/Nuitka/Nuitka/issues/3243),
  [Nuitka#3291](https://github.com/Nuitka/Nuitka/issues/3291)), not something fixable with flags.
  `pypdfium2` (ctypes bindings, no giant generated wrapper) compiles cleanly and is comparable in
  extraction speed. Test fixtures generate PDFs with `reportlab` (test-only dependency) instead.
- The Nuitka build in `main.py` needs `--low-memory --lto=no --include-qt-plugins=platforms` even
  with `pypdfium2` — `--enable-plugins=pyqt6` otherwise bundles every Qt plugin category
  (`wayland-*`, `egldeviceintegrations`, `tls`, `printsupport`, …) this app never uses, and LTO
  substantially raises peak compiler memory for onefile builds. Don't add `multiprocessing` to
  `--enable-plugins` — recent Nuitka versions enable that plugin unconditionally and warn if it's
  passed explicitly.
- The Nuitka pyqt6 plugin prints "Qt threading does not work, so prefer PySide6" on every build —
  this is stale/overbroad for our usage. Verified directly: a frozen binary's `QThread.run()`
  executes on a genuinely separate native thread ID, and the main event loop stays responsive
  while it runs. Don't take that warning as a reason to avoid `QThread` here.
- Any code path that mutates `file_names` or the keyword list must call
  `update_scan_button_state()` — there is no other single source of truth for whether the Scan
  button should be enabled (this was a real, previously-shipped bug).
- `openpyxl` (used for `.xlsx` export) was verified to compile cleanly with Nuitka's onefile
  backend (no repeat of the PyMuPDF `mupdf.py` OOM issue) — it's pure Python with only
  `et-xmlfile` as a transitive dependency, no giant generated wrapper module.
- Regex match mode: whitespace in the extracted text is deliberately left uncollapsed only in
  `MatchMode.REGEX` — Substring/Whole-word collapse whitespace runs (see `scanner.py`) so a
  multi-word keyword still matches text a PDF/DOCX line-wrap split across a newline. Regex mode
  is the power-user escape hatch and should see the real extracted text.
- `keyword_list` (`QListWidget`) has `setEditTriggers(NoEditTriggers)` — in-place editing of a
  keyword wouldn't refresh `file_headers`, the save-keywords button state, or regex-validity
  highlighting, so it's disabled rather than half-supported. Removing and re-adding is the
  supported way to change a keyword.
- Windows only targets Windows 10+ (Windows 10 is out of support, but still the floor). Style is
  forced to `QStyleFactory.create('windows11')` (Qt 6.7+, follows the Windows dark/light color
  scheme), falling back to `'fusion'` (also dark-mode aware) rather than Qt's old default
  `'windowsvista'` (which ignores dark mode entirely) — not verified against a real Windows
  build in this session, reasoned from Qt's documented style behavior.
- `options_dialog.Options`' color/text fields (`ScanDisplayOptions`) are persisted via
  `FileScanner`'s `QSettings` under `display/<field>` keys (colors round-tripped as hex strings),
  loaded in `__init__` via `_load_display_options()` and saved in `closeEvent` via
  `_save_display_options()`. `Options.refresh_widgets()` must be called after mutating
  `self.display` directly (bypassing the dialog's own setters) so the dialog's buttons/text
  inputs stay in sync with what's actually in effect.
- App icon (`assets/icon.svg` source, rasterized to `icon.png`/`icon.ico`) is loaded via
  `main_window.ICON_PATH = Path(__file__).resolve().parent / 'assets' / 'icon.png'` — resolves
  correctly both from source and in a Nuitka onefile build because `--include-data-files` (in
  `main.py`) places the file at that same relative path inside the runtime extraction dir. Windows
  additionally bakes the icon into the exe resource via `--windows-icon-from-ico`. There is no
  onefile equivalent on Linux — Nuitka's `--linux-icon` only applies with `--mode=app`/`app-dist`
  and is a silent no-op (with a warning) otherwise, so don't add it back; the Linux taskbar icon
  comes entirely from the runtime `QApplication.setWindowIcon()`/`FileScanner.setWindowIcon()`
  calls (the window manager reads that as the X11/Wayland icon hint). Keep the Windows flag and
  the `--include-data-files` line in sync with wherever `assets/icon.*` actually lives if it's
  ever moved. Verified: a real onefile build succeeds, `windowIcon().isNull()` is `False` at
  runtime, and the icon was confirmed rendering correctly in the taskbar of a real compiled
  Linux build. Not yet confirmed on real Windows in this session.
- `self.files` (`QTableWidget`) is both the pre-scan file list and the post-scan results grid —
  columns get appended onto the same rows, not a separate widget. With sorting enabled, row
  position no longer equals `file_names` list index, so nothing may capture a row index and trust
  it later. The fix in place: each row's file path lives in `Qt.ItemDataRole.UserRole`
  (`FILE_PATH_ROLE`) on its column-0 item, and `self.file_items: dict[str, QTableWidgetItem]` maps
  file → that item; `item.row()` always reflects the item's *current* visual position, so
  `handle_scan_result` looks up `self.file_items[result.file].row()` fresh each time rather than
  trusting a row captured earlier. `remove_files_clicked` reads the file off the row via
  `FILE_PATH_ROLE` and removes it from `file_names` by value (`list.remove`), never by position.
  Any new code touching `self.files` must follow the same rule.
- Sorting is deliberately turned off for the duration of a scan (`scan_files_clicked` /
  `handle_scan_finished`) — leaving it on would re-sort on every single incoming result (visible
  row-jumping mid-scan, and O(n² log n) work on the ~9000-file batches this app has hit before).
  It's re-enabled once the scan finishes. `_add_files` similarly disables sorting for its own bulk
  insert and restores whatever the setting was before (avoids an O(n log n) resort per appended
  row).
- The results-table filter (`self.filter_text` / `_apply_filter`) recomputes row visibility from
  each row's current cell content every time it runs, rather than tracking anything by row index —
  this is what keeps it correct regardless of what sorting did to row order, without needing to
  reason about whether Qt's per-row hidden state follows a row through a sort.
- PDF page numbers for a match: `scanner.extract_text` concatenates all pages' `pypdfium2` text
  (inserting one space at each page boundary — pypdfium2 doesn't add one itself, so without it the
  last word of one page could fuse with the first word of the next) and returns
  `(text, page_boundaries)`. Matching still happens against one whitespace-collapsed document (so
  a phrase split across a page break, or a line-wrap, still matches) — `_collapse_with_mapping`
  additionally returns `index_map`, translating a position in the collapsed text back to the raw
  text so `bisect.bisect_right(page_boundaries, ...)` can find the page. `.docx`/`.txt` return
  `page_boundaries=None` (`.docx` pagination is a print-time layout computation, not stored in the
  file at all; `.txt` has no pages) and their occurrences always report `page=None`.
- `_all_occurrences` caps collection at `MAX_OCCURRENCES_PER_KEYWORD` (20) and sets `truncated`
  rather than collecting every match unconditionally — a common word or a pathological regex
  matching at many/most positions in a large file must not blow up per-file scan time or tooltip
  size.
- `export_excel_clicked`'s cell-fill check must test `brush.style() == Qt.BrushStyle.NoBrush`, not
  `color.isValid() and color.alpha() > 0` — a `QTableWidgetItem` with no background ever set still
  reports its background color as opaque black (`alpha=255`, a "valid" `QColor`); only the brush
  *style* actually distinguishes "no background was set" from "black was explicitly set" (this was
  a real shipped bug: the filename column, which never gets a background, was rendering solid
  black in every exported `.xlsx`). Confirmed directly with a throwaway `QTableWidgetItem` — don't
  trust `color.alpha()` for this again.
- `self.file_occurrences: dict[str, list[list[Occurrence]]]` mirrors `self.file_items` — same
  reset points (cleared at scan start, populated per-file in `handle_scan_result`, popped in
  `remove_files_clicked`) — and is what `_ask_export_extra_columns`/`_export_rows` use to offer
  page-number/snippet columns on export. Keep it in sync wherever `file_items` is touched.
- `export_results_clicked`/`export_excel_clicked`/`save_keywords_clicked` all call
  `_ensure_extension` before writing — native save dialogs (particularly on Linux) don't reliably
  append the filter's extension if the user types a bare filename, so the code must not assume
  `target_path` already has one. Any future save-file dialog needs the same treatment.
- `export_excel_clicked` runs every row through `_sanitize_for_xlsx` before `sheet.append(...)` —
  extracted PDF text can contain characters XML 1.0 forbids outright (control chars, and
  noncharacters like `U+FFFE`) as decoding/font-substitution garbage, and openpyxl writes cell
  text straight into XML with no sanitizing of its own. Confirmed directly against a real
  user-exported file that hit this: the resulting `.xlsx` was corrupt enough that openpyxl
  couldn't even re-open its own output. This became reachable once snippets (raw extracted text)
  started flowing into export cells — CSV isn't affected (no XML well-formedness constraint), so
  the sanitizing only happens in the xlsx path, not in the shared `_export_rows` generator.
- Match mode (`MatchMode`) has two independent persistence paths, both needed:
  `_load_match_mode`/`_save_match_mode` (via `QSettings`, alongside display options/geometry —
  survives an app restart) and the `MATCH_MODE_MARKER_PREFIX` first line in a saved keyword file
  (survives loading that *specific* file into a session currently in a different mode). Before
  either existed, saving a keyword list built in Regex mode and loading it back later silently
  reinterpreted patterns like `\d{4,}` as literal (near-never-matching) substrings — a real
  shipped bug. A keyword file without the marker line (hand-written, or saved before this existed)
  intentionally leaves whatever mode is already active alone rather than resetting it.

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
- `tests/conftest.py`'s `make_multipage_pdf` (used by the `multipage_pdf_file`/
  `split_phrase_pdf_file` fixtures) calls `canvas.showPage()` between pages — needed for a
  genuinely multi-page PDF; `make_pdf`'s single `drawString` call only ever produces one page.
- `QTableWidget.setSortingEnabled(True)` does not itself trigger a sort — confirmed directly (see
  a throwaway repro in this session's history): rows stay in insertion order until a header is
  actually clicked or `sortItems()` is called, even when re-enabling sorting after a bulk insert
  that had it temporarily off. Don't assume otherwise without checking again if this ever seems to
  misbehave — it's the kind of Qt behavior that's easy to get backwards from memory.

## Versioning
Version is derived from git tags via `setuptools-scm` (see `[tool.setuptools_scm]` in
`pyproject.toml`) — never hand-edit a version number in the code.

## Backlog (deliberately deferred, not TODOs to pick up unprompted)
Session save/load, dark-mode consistency on Linux.
