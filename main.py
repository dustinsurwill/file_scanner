# nuitka-project: --onefile
# nuitka-project: --output-filename=file-scanner
# nuitka-project: --enable-plugins=pyqt6
# nuitka-project: --include-qt-plugins=platforms
# nuitka-project: --low-memory
# nuitka-project: --lto=no
# nuitka-project: --include-data-files=assets/icon.png=assets/icon.png
# nuitka-project-if: {OS} == "Windows":
#    nuitka-project: --windows-console-mode=disable
#    nuitka-project: --windows-icon-from-ico=assets/icon.ico
# Linux has no equivalent onefile flag - '--linux-icon' only applies with
# --mode=app/app-dist (Nuitka warns and no-ops otherwise). The runtime
# app.setWindowIcon()/setWindowIcon() calls below are what set the taskbar
# icon on Linux (via the window manager's X11/Wayland icon hint).

import sys
from multiprocessing import freeze_support
from os.path import isfile

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from main_window import ICON_PATH, FileScanner

if __name__ == '__main__':
    freeze_support()
    app = QApplication(sys.argv)
    if isfile(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    window = FileScanner()
    window.show()
    sys.exit(app.exec())
