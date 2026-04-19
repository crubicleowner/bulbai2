from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from bulbopt.app.main import build_cli_banner
from bulbopt.application.contracts.models import CaseSummary
from bulbopt.ui.desktop.case_wizard import default_case_payload, discover_demo_source_path
from bulbopt.ui.desktop.main_window import MainWindow
import bulbopt.ui.desktop.main_window as main_window_module


def test_discover_demo_source_path_finds_repo_docs_asset() -> None:
    source_path = Path(discover_demo_source_path())

    assert source_path.name == "base_hull.stl"
    assert source_path.exists()


def test_desktop_shell_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication([])
    window = MainWindow(project_root=tmp_path / "projects")

    try:
        assert build_cli_banner().endswith("STL-first vertical slice")
        assert default_case_payload()["import_format"] == "stl"
        assert default_case_payload()["optimization_mode"] == "generate_new_bulb"
        assert Path(str(default_case_payload()["source_path"])).name == "base_hull.stl"
        assert window.windowTitle() == "BulbOpt Desktop"
        assert window.services["settings"].project_root == tmp_path / "projects"

        central_widget = window.centralWidget()
        assert central_widget is not None

        app_name = central_widget.findChild(QLabel, "app_name_label")
        ready_state = central_widget.findChild(QLabel, "ready_state_label")
        source_path = central_widget.findChild(QLabel, "source_path_label")
        run_button = central_widget.findChild(QPushButton, "run_vertical_slice_button")
        run_status = central_widget.findChild(QLabel, "run_status_label")
        artifacts_label = central_widget.findChild(QLabel, "artifacts_label")

        assert app_name is not None
        assert ready_state is not None
        assert source_path is not None
        assert run_button is not None
        assert run_status is not None
        assert artifacts_label is not None
        assert app_name.text() == "BulbOpt Desktop"
        assert "Ready" in ready_state.text()
        assert "base_hull.stl" in source_path.text()
        assert "Idle" in run_status.text()
        assert "No artifacts yet" in artifacts_label.text()
    finally:
        window.close()
        app.processEvents()


def test_main_window_runs_vertical_slice_from_button(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    captured: dict[str, object] = {}

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return CaseSummary(
            case_id="case-001",
            case_name=str(kwargs["case_name"]),
            status="completed",
            best_candidate_id="cand-1",
        )

    def fake_bootstrap(project_root: Path) -> dict[str, object]:
        return {
            "settings": SimpleNamespace(project_root=project_root),
            "run_vertical_slice": fake_runner,
        }

    monkeypatch.setattr(main_window_module, "bootstrap_application", fake_bootstrap)

    app = QApplication.instance() or QApplication([])
    window = MainWindow(project_root=tmp_path / "projects")

    try:
        central_widget = window.centralWidget()
        assert central_widget is not None

        run_button = central_widget.findChild(QPushButton, "run_vertical_slice_button")
        run_status = central_widget.findChild(QLabel, "run_status_label")
        artifacts_label = central_widget.findChild(QLabel, "artifacts_label")

        assert run_button is not None
        assert run_status is not None
        assert artifacts_label is not None

        run_button.click()
        app.processEvents()

        assert captured["case_name"] == "stl-demo"
        assert Path(str(captured["source_path"])).name == "base_hull.stl"
        assert "Completed" in run_status.text()
        assert "cand-1" in run_status.text()
        assert "case-001" in artifacts_label.text()
        assert "report.html" in artifacts_label.text()
    finally:
        window.close()
        app.processEvents()
