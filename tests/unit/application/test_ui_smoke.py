from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel

from bulbopt.app.main import build_cli_banner
from bulbopt.ui.desktop.case_wizard import default_case_payload
from bulbopt.ui.desktop.main_window import MainWindow


def test_desktop_shell_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication([])
    window = MainWindow(project_root=tmp_path / "projects")

    try:
        assert build_cli_banner().endswith("STL-first vertical slice")
        assert default_case_payload()["import_format"] == "stl"
        assert default_case_payload()["optimization_mode"] == "generate_new_bulb"
        assert window.windowTitle() == "BulbOpt Desktop"
        assert window.services["settings"].project_root == tmp_path / "projects"

        central_widget = window.centralWidget()
        assert central_widget is not None

        app_name = central_widget.findChild(QLabel, "app_name_label")
        ready_state = central_widget.findChild(QLabel, "ready_state_label")

        assert app_name is not None
        assert ready_state is not None
        assert app_name.text() == "BulbOpt Desktop"
        assert "Ready" in ready_state.text()
    finally:
        window.close()
        app.processEvents()
