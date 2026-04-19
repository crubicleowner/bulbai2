from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton, QDoubleSpinBox, QLineEdit, QSpinBox

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
        execution_summary = central_widget.findChild(QLabel, "execution_summary_label")
        weights_summary = central_widget.findChild(QLabel, "weights_summary_label")
        hydrostatics_summary = central_widget.findChild(QLabel, "hydrostatics_summary_label")
        optimization_summary = central_widget.findChild(QLabel, "optimization_summary_label")
        candidates_summary = central_widget.findChild(QLabel, "candidates_summary_label")
        candidates_list = central_widget.findChild(QListWidget, "candidates_list_widget")
        open_case_button = central_widget.findChild(QPushButton, "open_case_button")
        open_report_button = central_widget.findChild(QPushButton, "open_report_button")
        open_best_button = central_widget.findChild(QPushButton, "open_best_candidate_button")

        assert app_name is not None
        assert ready_state is not None
        assert source_path is not None
        assert run_button is not None
        assert run_status is not None
        assert artifacts_label is not None
        assert results_label is not None
        assert geometry_summary is not None
        assert evaluation_summary is not None
        assert execution_summary is not None
        assert weights_summary is not None
        assert hydrostatics_summary is not None
        assert optimization_summary is not None
        assert candidates_summary is not None
        assert candidates_list is not None
        assert open_case_button is not None
        assert open_report_button is not None
        assert open_best_button is not None
        assert app_name.text() == "BulbOpt Desktop"
        assert "Ready" in ready_state.text()
        assert "base_hull.stl" in source_path.text()
        assert "Idle" in run_status.text()
        assert "No artifacts yet" in artifacts_label.text()
        assert "Results" in results_label.text()
        assert "not available" in geometry_summary.text()
        assert "not available" in evaluation_summary.text()
        assert "not available" in execution_summary.text()
        assert "not available" in weights_summary.text()
        assert "not available" in hydrostatics_summary.text()
        assert "not available" in optimization_summary.text()
        assert "not available" in candidates_summary.text()
        assert candidates_list.count() == 0
        assert open_case_button.isEnabled() is False
        assert open_report_button.isEnabled() is False
        assert open_best_button.isEnabled() is False
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
        candidate_count = wizard.findChild(QSpinBox, "candidate_count_input")
        resistance_weight = wizard.findChild(QDoubleSpinBox, "resistance_weight_input")
        axial_gain_weight = wizard.findChild(QDoubleSpinBox, "axial_gain_weight_input")

        assert case_name is not None
        assert source_path is not None
        assert beam is not None
        assert runtime is not None
        assert candidate_count is not None
        assert resistance_weight is not None
        assert axial_gain_weight is not None

        case_name.setText("edited-demo")
        source_path.setText("C:/demo/custom.stl")
        beam.setValue(22.4)
        runtime.setValue(10)
        candidate_count.setValue(5)
        resistance_weight.setValue(1.4)
        axial_gain_weight.setValue(0.2)

        payload = wizard.payload()

        assert payload["case_name"] == "edited-demo"
        assert payload["source_path"] == "C:/demo/custom.stl"
        assert payload["vessel_beam_m"] == 22.4
        assert payload["runtime_budget_hours"] == 10
        assert payload["candidate_count"] == 5
        assert payload["resistance_weight"] == 1.4
        assert payload["axial_gain_weight"] == 0.2
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
                "execution": "Execution summary: runtime=8 h candidates=3 processed=3",
                "weights": "Objective weights: resistance=1.0 axial=0.8 draft=0.1 beam=0.05",
                "hydrostatics": "Hydrostatics-lite: status=ok volume_delta=1.2% draft_delta=0.03 penalty=0.18",
                "optimization": "Optimization summary: best=cand-1 ranked=3 spread=2.0",
                "candidates": "Candidates: cand-1 mid=9.0 | cand-2 mid=8.0 | cand-3 mid=7.0",
                "candidate_rows": [
                    "cand-1 | fast=1.0 | mid=9.0",
                    "cand-2 | fast=0.9 | mid=8.0",
                    "cand-3 | fast=0.8 | mid=7.0",
                ],
                "best_candidate_path": tmp_path / "projects" / "case-001" / "working" / "candidates" / "cand-1.stl",
            },
        )

        central_widget = window.centralWidget()
        assert central_widget is not None

        run_button = central_widget.findChild(QPushButton, "run_vertical_slice_button")
        run_status = central_widget.findChild(QLabel, "run_status_label")
        artifacts_label = central_widget.findChild(QLabel, "artifacts_label")
        geometry_summary = central_widget.findChild(QLabel, "geometry_summary_label")
        evaluation_summary = central_widget.findChild(QLabel, "evaluation_summary_label")
        execution_summary = central_widget.findChild(QLabel, "execution_summary_label")
        weights_summary = central_widget.findChild(QLabel, "weights_summary_label")
        hydrostatics_summary = central_widget.findChild(QLabel, "hydrostatics_summary_label")
        optimization_summary = central_widget.findChild(QLabel, "optimization_summary_label")
        candidates_summary = central_widget.findChild(QLabel, "candidates_summary_label")
        candidates_list = central_widget.findChild(QListWidget, "candidates_list_widget")
        open_case_button = central_widget.findChild(QPushButton, "open_case_button")
        open_report_button = central_widget.findChild(QPushButton, "open_report_button")
        open_best_button = central_widget.findChild(QPushButton, "open_best_candidate_button")

        assert run_button is not None
        assert run_status is not None
        assert artifacts_label is not None
        assert geometry_summary is not None
        assert evaluation_summary is not None
        assert execution_summary is not None
        assert weights_summary is not None
        assert hydrostatics_summary is not None
        assert optimization_summary is not None
        assert candidates_summary is not None
        assert candidates_list is not None
        assert open_case_button is not None
        assert open_report_button is not None
        assert open_best_button is not None

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
        assert "runtime=8 h" in execution_summary.text()
        assert "processed=3" in execution_summary.text()
        assert "axial=0.8" in weights_summary.text()
        assert "status=ok" in hydrostatics_summary.text()
        assert "volume_delta=1.2%" in hydrostatics_summary.text()
        assert "best=cand-1" in optimization_summary.text()
        assert "ranked=3" in optimization_summary.text()
        assert "cand-2" in candidates_summary.text()
        assert "cand-3" in candidates_summary.text()
        assert candidates_list.count() == 3
        assert "cand-2" in candidates_list.item(1).text()
        assert open_case_button.isEnabled() is True
        assert open_report_button.isEnabled() is True
        assert open_best_button.isEnabled() is True
    finally:
        window.close()
        app.processEvents()


def test_main_window_surfaces_completed_with_warnings_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    def fake_runner(**kwargs):
        return CaseSummary(
            case_id="case-301",
            case_name=str(kwargs["case_name"]),
            status="completed_with_warnings",
            best_candidate_id="cand-warn",
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
                "evaluation": "Evaluation summary: cand-warn fast=1.0 mid=0.5 resistance=4.08",
                "execution": "Execution summary: runtime=8 h candidates=3 processed=3",
                "weights": "Objective weights: resistance=1.0 axial=0.8 draft=0.1 beam=0.05",
                "hydrostatics": "Hydrostatics-lite: status=warn volume_delta=5.0% draft_delta=0.08 penalty=0.58",
                "optimization": "Optimization summary: best=cand-warn ranked=3 spread=0.7",
                "candidates": "Candidates: cand-warn mid=0.5 | cand-2 mid=1.2 | cand-3 mid=1.4",
                "candidate_rows": [
                    "cand-warn | fast=1.0 | mid=0.5",
                    "cand-2 | fast=0.9 | mid=1.2",
                    "cand-3 | fast=0.8 | mid=1.4",
                ],
                "best_candidate_path": tmp_path / "projects" / "case-301" / "working" / "candidates" / "cand-warn.stl",
            },
        )

        central_widget = window.centralWidget()
        assert central_widget is not None
        run_button = central_widget.findChild(QPushButton, "run_vertical_slice_button")
        run_status = central_widget.findChild(QLabel, "run_status_label")
        hydrostatics_summary = central_widget.findChild(QLabel, "hydrostatics_summary_label")

        assert run_button is not None
        assert run_status is not None
        assert hydrostatics_summary is not None

        run_button.click()
        app.processEvents()

        assert "completed_with_warnings" in run_status.text()
        assert "status=warn" in hydrostatics_summary.text()
    finally:
        window.close()
        app.processEvents()


def test_main_window_opens_case_report_and_best_candidate_artifacts(tmp_path: Path, monkeypatch) -> None:
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
        open_best_button = central_widget.findChild(QPushButton, "open_best_candidate_button")

        assert run_button is not None
        assert open_case_button is not None
        assert open_report_button is not None
        assert open_best_button is not None

        case_dir = tmp_path / "projects" / "case-101"
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "artifacts_index.json").write_text(
            '{"best_candidate_stl":"'
            + str(case_dir / "working" / "candidates" / "cand-7.stl").replace("\\", "\\\\")
            + '"}',
            encoding="utf-8",
        )

        run_button.click()
        open_case_button.click()
        open_report_button.click()
        open_best_button.click()
        app.processEvents()

        assert opened_paths == [
            tmp_path / "projects" / "case-101",
            tmp_path / "projects" / "case-101" / "outputs" / "reports" / "report.html",
            tmp_path / "projects" / "case-101" / "working" / "candidates" / "cand-7.stl",
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
        (case_dir / "metadata.json").write_text(
            (
                '{"create_case_command":{"runtime_budget_hours":12,"candidate_count":5}}'
            ),
            encoding="utf-8",
        )
        (case_dir / "working" / "evaluation").mkdir(parents=True)
        (case_dir / "working" / "evaluation" / "optimization_summary.json").write_text(
            (
                '{"best_candidate_id":"candidate-3","ranked_count":2,'
                '"best_mid_score":7.0,"worst_mid_score":8.1,"mid_score_spread":1.1}'
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
        assert "candidate-3" in results["optimization"]
        assert "ranked=2" in results["optimization"]
        assert "spread=1.1" in results["optimization"]
        assert "candidate-1" in results["candidates"]
        assert "candidate-3" in results["candidates"]
        assert "mid=8.1" in results["candidates"]
        assert "runtime=12 h" in results["execution"]
        assert "candidates=5" in results["execution"]
        assert "processed=2" in results["execution"]
        assert len(results["candidate_rows"]) == 2
        assert "candidate-1" in results["candidate_rows"][0]
    finally:
        window.close()
        app.processEvents()


def test_main_window_loads_case_results_from_case_summary_metrics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication([])
    window = MainWindow(project_root=tmp_path / "projects")

    try:
        case_dir = tmp_path / "projects" / "case-888"
        case_dir.mkdir(parents=True)
        (case_dir / "case.json").write_text(
            (
                '{'
                '"summary_metrics":{'
                '"geometry":{"vertices_count":999,"faces_count":111,"watertight":true,"primary_axis":0,"slenderness_ratio":6.2},'
                '"evaluation":{"best_candidate_id":"candidate-9","fast_score":0.2,"mid_score":1.5,"resistance_proxy":3.14},'
                '"hydrostatics":{"volume_delta_pct":1.1,"draft_delta_m":0.02,"hydrostatic_penalty":0.15,"constraint_status":"ok","warnings":[]},'
                '"execution":{"runtime_budget_hours":7,"candidate_count":4,"processed_candidates":4},'
                '"objective_weights":{"resistance_weight":1.1,"axial_gain_weight":0.3,"draft_reduction_weight":0.05,"beam_growth_weight":0.2},'
                '"optimization":{"best_candidate_id":"candidate-9","ranked_count":4,"mid_score_spread":0.8},'
                '"candidates":{"summary":"Candidates: candidate-9 mid=1.5 | candidate-7 mid=2.3","rows":["candidate-9 | fast=0.2 | mid=1.5","candidate-7 | fast=0.3 | mid=2.3"]}'
                '}'
                '}'
            ),
            encoding="utf-8",
        )

        results = window._load_case_results(case_dir, "candidate-9")

        assert "999" in results["geometry"]
        assert "111" in results["geometry"]
        assert "slenderness=6.2" in results["geometry"]
        assert "candidate-9" in results["evaluation"]
        assert "resistance=3.14" in results["evaluation"]
        assert "runtime=7 h" in results["execution"]
        assert "processed=4" in results["execution"]
        assert "resistance=1.1" in results["weights"]
        assert "beam=0.2" in results["weights"]
        assert "status=ok" in results["hydrostatics"]
        assert "volume_delta=1.1%" in results["hydrostatics"]
        assert "penalty=0.15" in results["hydrostatics"]
        assert "best=candidate-9" in results["optimization"]
        assert "ranked=4" in results["optimization"]
        assert "spread=0.8" in results["optimization"]
        assert "candidate-7" in results["candidates"]
        assert len(results["candidate_rows"]) == 2
    finally:
        window.close()
        app.processEvents()
