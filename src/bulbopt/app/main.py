from __future__ import annotations

import os
from pathlib import Path
import sys


def build_cli_banner() -> str:
    return "BulbOpt Desktop | STL-first vertical slice"


def default_project_root() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "BulbOpt" / "projects"
    return Path.home() / ".bulbopt" / "projects"


def run_desktop() -> int:
    from PySide6.QtWidgets import QApplication

    from bulbopt.ui.desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(project_root=default_project_root())
    window.show()
    return app.exec()


def dispatch_main(
    run_shell=run_desktop,
    print_banner=print,
    launched_as_module: bool | None = None,
) -> int:
    if launched_as_module is None:
        launched_as_module = __spec__ is not None

    if launched_as_module:
        return run_shell()

    print_banner(build_cli_banner())
    return 0


if __name__ == "__main__":
    raise SystemExit(dispatch_main())
