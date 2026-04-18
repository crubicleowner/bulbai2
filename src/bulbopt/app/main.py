from __future__ import annotations

from pathlib import Path
import sys


def build_cli_banner() -> str:
    return "BulbOpt Desktop | STL-first vertical slice"


def run_desktop() -> int:
    from PySide6.QtWidgets import QApplication

    from bulbopt.ui.desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(project_root=Path("bulbopt_projects"))
    window.show()
    return app.exec()


if __name__ == "__main__":
    print(build_cli_banner())
