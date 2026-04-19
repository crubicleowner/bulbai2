from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QDoubleSpinBox, QLineEdit, QSpinBox

from bulbopt.app.main import build_cli_banner
from bulbopt.application.contracts.models import CaseSummary
from bulbopt.ui.desktop.case_wizard import CaseWizard, default_case_payload, discover_demo_source_path
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
        results_label = central_widget.findChild(QLabel, "results_panel_label")
        geometry_summary = central_widget.findChild(QLabel, "geometry_summary_label")
        evaluation_summary = central_widget.findChild(QLabel, "evaluation_summary_label")
        candidates_summary = central_widget.findChild(QLabel, "candidates_summary_label")
        open_case_button = central_widget.findChild(QPushButton, "open_case_button")
        open_report_button = central_widget.findChild(QPushButton, "open_report_button")

        assert app_name is not None
        assert ready_state is not None
        assert source_path is not None
        assert run_button is not None
        assert run_status is not None
        assert artifacts_label is not None
        assert results_label is not None
        assert geometry_summary is not None
        assert evaluation_summary is not None
        assert candidates_summary is not None
        assert open_case_button is not None
        assert open_report_button is not None
        assert app_name.text() == "BulbOpt Desktop"
        assert "Ready" in ready_state.text()
        assert "base_hull.stl" in source_path.text()
        assert "Idle" in run_status.text()
        assert "No artifacts yet" in artifacts_label.text()
        assert "Results" in results_label.text()
        assert "not available" in geometry_summary.text()
        assert "not available" in evaluation_summary.text()
        assert "not available" in candidates_summary.text()
        assert open_case_button.isEnabled() is False
        assert open_report_button.isEnabled() is False
    finally:
        window.close()
        app.processEvents()


def test_case_wizard_payload_reflects_user_edits(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication([])
    wizard = CaseWizard()

    try:
        case_name = wizard.findChild(QLineEdit, "case_name_input")
        source_path = wizard.findChild(QLineEdit, "source_path_input")
        beam = wizard.findChild(QDoubleSpinBox, "vessel_beam_input")
        runtime = wizard.findChild(QSpinBox, "runtime_budget_input")

        assert case_name is not None
        assert source_path is not None
        assert beam is not None
        assert runtime is not None

        case_name.setText("edited-demo")
        source_path.setText("C:/demo/custom.stl")
        beam.setValue(22.4)
        runtime.setValue(10)

        payload = wizard.payload()

        assert payload["case_name"] == "edited-demo"
        assert payload["source_path"] == "C:/demo/custom.stl"
        assert payload["vessel_beam_m"] == 22.4
        assert payload["runtime_budget_hours"] == 10
    finally:
        wizard.close()
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
        monkeypatch.setattr(
            window,
            "_load_case_results",
            lambda case_dir, best_candidate_id: {
                "geometry": "Geometry summary: V=120 F=240 watertight=no axis=0 slenderness=7.5",
                "evaluation": "Evaluation summary: cand-1 fast=1.0 mid=9.0 resistance=4.08",
                "candidates": "Candidates: cand-1 mid=9.0 | cand-2 mid=8.0 | cand-3 mid=7.0",
            },
        )

        central_widget = window.centralWidget()
        assert central_widget is not None

        run_button = central_widget.findChild(QPushButton, "run_vertical_slice_button")
        run_status = central_widget.findChild(QLabel, "run_status_label")
        artifacts_label = central_widget.findChild(QLabel, "artifacts_label")
        geometry_summary = central_widget.findChild(QLabel, "geometry_summary_label")
        evaluation_summary = central_widget.findChild(QLabel, "evaluation_summary_label")
        candidates_summary = central_widget.findChild(QLabel, "candidates_summary_label")
        open_case_button = central_widget.findChild(QPushButton, "open_case_button")
        open_report_button = central_widget.findChild(QPushButton, "open_report_button")

        assert run_button is not None
        assert run_status is not None
        assert artifacts_label is not None
        assert geometry_summary is not None
        assert evaluation_summary is not None
        assert candidates_summary is not None
        assert open_case_button is not None
        assert open_report_button is not None

        run_button.click()
        app.processEvents()

        assert captured["case_name"] == "stl-demo"
        assert Path(str(captured["source_path"])).name == "base_hull.stl"
        assert "Completed" in run_status.text()
        assert "cand-1" in run_status.text()
        assert "case-001" in artifacts_label.text()
        assert "report.html" in artifacts_label.text()
        assert "V=120" in geometry_summary.text()
        assert "slenderness=7.5" in geometry_summary.text()
        assert "cand-1" in evaluation_summary.text()
        assert "resistance=4.08" in evaluation_summary.text()
        assert "cand-2" in candidates_summary.text()
        assert "cand-3" in candidates_summary.text()
        assert open_case_button.isEnabled() is True
        assert open_report_button.isEnabled() is True
    finally:
        window.close()
        app.processEvents()


def test_main_window_opens_case_and_report_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    opened_paths: list[Path] = []

    def fake_runner(**kwargs):
        return CaseSummary(
            case_id="case-101",
            case_name=str(kwargs["case_name"]),
            status="completed",
            best_candidate_id="cand-7",
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
        monkeypatch.setattr(window, "_open_path", lambda path: opened_paths.append(path))

        central_widget = window.centralWidget()
        assert central_widget is not None

        run_button = central_widget.findChild(QPushButton, "run_vertical_slice_button")
        open_case_button = central_widget.findChild(QPushButton, "open_case_button")
        open_report_button = central_widget.findChild(QPushButton, "open_report_button")

        assert run_button is not None
        assert open_case_button is not None
        assert open_report_button is not None

        run_button.click()
        open_case_button.click()
        open_report_button.click()
        app.processEvents()

        assert opened_paths == [
            tmp_path / "projects" / "case-101",
            tmp_path / "projects" / "case-101" / "outputs" / "reports" / "report.html",
        ]
    finally:
        window.close()
        app.processEvents()


def test_main_window_loads_case_results_from_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication([])
    window = MainWindow(project_root=tmp_path / "projects")

    try:
        case_dir = tmp_path / "projects" / "case-777"
        (case_dir / "working" / "repaired").mkdir(parents=True)
        (case_dir / "evaluation_index.json").write_text(
            (
                '['
                '{"candidate_id":"candidate-1","fast_score":0.31,"mid_score":8.1,'
                '"geometry_metrics":{"slenderness_ratio":7.2},'
                '"score_components":{"resistance_proxy":0.255}},'
                '{"candidate_id":"candidate-3","fast_score":0.333,"mid_score":7.0,'
                '"geometry_metrics":{"slenderness_ratio":7.6},'
                '"score_components":{"resistance_proxy":0.244}}'
                ']'
            ),
            encoding="utf-8",
        )
        (case_dir / "working" / "repaired" / "geometry_analysis.json").write_text(
            (
                '{"quality_report":{"vertices_count":14638,"faces_count":29272,'
                '"watertight":false,"primary_axis":0}}'
            ),
            encoding="utf-8",
        )

        results = window._load_case_results(case_dir, "candidate-3")

        assert "14638" in results["geometry"]
        assert "29272" in results["geometry"]
        assert "7.6" in results["geometry"]
        assert "candidate-3" in results["evaluation"]
        assert "7.0" in results["evaluation"]
        assert "0.244" in results["evaluation"]
        assert "candidate-1" in results["candidates"]
        assert "candidate-3" in results["candidates"]
        assert "mid=8.1" in results["candidates"]
    finally:
        window.close()
        app.processEvents()
