# nuitka-project: --onefile
# nuitka-project: --enable-plugins=pyqt6
# nuitka-project: --include-qt-plugins=platforms
# nuitka-project: --low-memory
# nuitka-project: --lto=no
# nuitka-project-if: {OS} == "Windows":
#    nuitka-project: --windows-console-mode=disable

import sys
from multiprocessing import freeze_support

from PyQt6.QtWidgets import QApplication

from main_window import FileScanner

if __name__ == '__main__':
    freeze_support()
    app = QApplication(sys.argv)
    window = FileScanner()
    window.show()
    sys.exit(app.exec())
