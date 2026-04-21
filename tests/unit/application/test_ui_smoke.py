from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QListWidget,
    QPushButton,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
    QTableWidget,
)

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
        thresholds_summary = central_widget.findChild(QLabel, "acceptability_thresholds_summary_label")
        hydrostatics_summary = central_widget.findChild(QLabel, "hydrostatics_summary_label")
        calm_water_summary = central_widget.findChild(QLabel, "calm_water_summary_label")
        wave_response_summary = central_widget.findChild(QLabel, "wave_response_summary_label")
        baseline_summary = central_widget.findChild(QLabel, "baseline_summary_label")
        multi_condition_summary = central_widget.findChild(QLabel, "multi_condition_summary_label")
        high_fidelity_boundary_summary = central_widget.findChild(QLabel, "high_fidelity_boundary_summary_label")
        acceptability_summary = central_widget.findChild(QLabel, "acceptability_summary_label")
        optimization_summary = central_widget.findChild(QLabel, "optimization_summary_label")
        candidates_summary = central_widget.findChild(QLabel, "candidates_summary_label")
        rejected_candidates_summary = central_widget.findChild(QLabel, "rejected_candidates_summary_label")
        candidates_list = central_widget.findChild(QListWidget, "candidates_list_widget")
        rejected_candidates_list = central_widget.findChild(QListWidget, "rejected_candidates_list_widget")
        candidates_table = central_widget.findChild(QTableWidget, "candidates_table_widget")
        candidate_filter = central_widget.findChild(QComboBox, "candidate_filter_combo")
        candidate_filter_summary = central_widget.findChild(QLabel, "candidate_filter_summary_label")
        optimization_trace_summary = central_widget.findChild(QLabel, "optimization_trace_summary_label")
        optimization_trace_list = central_widget.findChild(QListWidget, "optimization_trace_list_widget")
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
        assert thresholds_summary is not None
        assert hydrostatics_summary is not None
        assert calm_water_summary is not None
        assert wave_response_summary is not None
        assert baseline_summary is not None
        assert multi_condition_summary is not None
        assert high_fidelity_boundary_summary is not None
        assert acceptability_summary is not None
        assert optimization_summary is not None
        assert candidates_summary is not None
        assert rejected_candidates_summary is not None
        assert candidates_list is not None
        assert rejected_candidates_list is not None
        assert candidates_table is not None
        assert candidate_filter is not None
        assert candidate_filter_summary is not None
        assert optimization_trace_summary is not None
        assert optimization_trace_list is not None
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
        assert "not available" in thresholds_summary.text()
        assert "not available" in hydrostatics_summary.text()
        assert "not available" in calm_water_summary.text()
        assert "not available" in wave_response_summary.text()
        assert "not available" in baseline_summary.text()
        assert "not available" in multi_condition_summary.text()
        assert "not available" in high_fidelity_boundary_summary.text()
        assert "not available" in acceptability_summary.text()
        assert "not available" in optimization_summary.text()
        assert "not available" in candidates_summary.text()
        assert "not available" in rejected_candidates_summary.text()
        assert "not available" in optimization_trace_summary.text()
        assert candidates_list.count() == 0
        assert rejected_candidates_list.count() == 0
        assert candidates_table.rowCount() == 0
        assert candidates_table.columnCount() == 9
        assert candidates_table.isSortingEnabled() is True
        assert candidate_filter.count() == 3
        assert candidate_filter.currentText() == "All"
        assert "0/0" in candidate_filter_summary.text()
        assert optimization_trace_list.count() == 0
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
        speed_profile = wizard.findChild(QLineEdit, "speed_profile_input")
        operational_profile = wizard.findChild(QLineEdit, "operational_profile_input")
        wave_height = wizard.findChild(QDoubleSpinBox, "wave_height_input")
        wave_period = wizard.findChild(QDoubleSpinBox, "wave_period_input")
        wave_scenario_heights = wizard.findChild(QLineEdit, "wave_scenario_heights_input")
        wave_scenario_periods = wizard.findChild(QLineEdit, "wave_scenario_periods_input")
        wave_scenario_weights = wizard.findChild(QLineEdit, "wave_scenario_weights_input")
        calm_condition_weight = wizard.findChild(QDoubleSpinBox, "calm_water_condition_weight_input")
        wave_condition_weight = wizard.findChild(QDoubleSpinBox, "wave_condition_weight_input")
        max_volume_delta = wizard.findChild(QDoubleSpinBox, "max_volume_delta_pct_input")
        max_draft_delta = wizard.findChild(QDoubleSpinBox, "max_draft_delta_m_input")
        max_speed_balance = wizard.findChild(QDoubleSpinBox, "max_speed_balance_ratio_input")
        max_wave_penalty = wizard.findChild(QDoubleSpinBox, "max_wave_penalty_input")
        reject_volume_delta = wizard.findChild(QDoubleSpinBox, "reject_volume_delta_pct_input")
        reject_draft_delta = wizard.findChild(QDoubleSpinBox, "reject_draft_delta_m_input")
        reject_speed_balance = wizard.findChild(QDoubleSpinBox, "reject_speed_balance_ratio_input")
        reject_wave_penalty = wizard.findChild(QDoubleSpinBox, "reject_wave_penalty_input")
        resistance_weight = wizard.findChild(QDoubleSpinBox, "resistance_weight_input")
        axial_gain_weight = wizard.findChild(QDoubleSpinBox, "axial_gain_weight_input")

        assert case_name is not None
        assert source_path is not None
        assert beam is not None
        assert runtime is not None
        assert candidate_count is not None
        assert speed_profile is not None
        assert operational_profile is not None
        assert wave_height is not None
        assert wave_period is not None
        assert wave_scenario_heights is not None
        assert wave_scenario_periods is not None
        assert wave_scenario_weights is not None
        assert calm_condition_weight is not None
        assert wave_condition_weight is not None
        assert max_volume_delta is not None
        assert max_draft_delta is not None
        assert max_speed_balance is not None
        assert max_wave_penalty is not None
        assert reject_volume_delta is not None
        assert reject_draft_delta is not None
        assert reject_speed_balance is not None
        assert reject_wave_penalty is not None
        assert resistance_weight is not None
        assert axial_gain_weight is not None

        case_name.setText("edited-demo")
        source_path.setText("C:/demo/custom.stl")
        beam.setValue(22.4)
        runtime.setValue(10)
        candidate_count.setValue(5)
        speed_profile.setText("16, 20, 24")
        operational_profile.setText("0.2, 0.3, 0.5")
        wave_height.setValue(1.8)
        wave_period.setValue(7.5)
        wave_scenario_heights.setText("1.0, 2.0")
        wave_scenario_periods.setText("6.0, 8.0")
        wave_scenario_weights.setText("0.25, 0.75")
        calm_condition_weight.setValue(0.55)
        wave_condition_weight.setValue(0.45)
        max_volume_delta.setValue(3.2)
        max_draft_delta.setValue(0.04)
        max_speed_balance.setValue(2.5)
        max_wave_penalty.setValue(1.1)
        reject_volume_delta.setValue(6.4)
        reject_draft_delta.setValue(0.08)
        reject_speed_balance.setValue(5.0)
        reject_wave_penalty.setValue(2.2)
        resistance_weight.setValue(1.4)
        axial_gain_weight.setValue(0.2)

        payload = wizard.payload()

        assert payload["case_name"] == "edited-demo"
        assert payload["source_path"] == "C:/demo/custom.stl"
        assert payload["vessel_beam_m"] == 22.4
        assert payload["runtime_budget_hours"] == 10
        assert payload["candidate_count"] == 5
        assert payload["speed_knots"] == [16.0, 20.0, 24.0]
        assert payload["operational_profile_weights"] == [0.2, 0.3, 0.5]
        assert payload["wave_height_m"] == 1.8
        assert payload["wave_period_s"] == 7.5
        assert payload["wave_scenario_heights_m"] == [1.0, 2.0]
        assert payload["wave_scenario_periods_s"] == [6.0, 8.0]
        assert payload["wave_scenario_weights"] == [0.25, 0.75]
        assert payload["calm_water_condition_weight"] == 0.55
        assert payload["wave_condition_weight"] == 0.45
        assert payload["max_volume_delta_pct"] == 3.2
        assert payload["max_draft_delta_m"] == 0.04
        assert payload["max_speed_balance_ratio"] == 2.5
        assert payload["max_wave_penalty"] == 1.1
        assert payload["reject_volume_delta_pct"] == 6.4
        assert payload["reject_draft_delta_m"] == 0.08
        assert payload["reject_speed_balance_ratio"] == 5.0
        assert payload["reject_wave_penalty"] == 2.2
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
                "operational_profile": "Operational profile: source=user_defined dominant=20.0 speeds=18.0,20.0 weights=0.4,0.6",
                "weights": "Objective weights: resistance=1.0 axial=0.8 draft=0.1 beam=0.05 calm=0.55 wave=0.45",
                "thresholds": "Acceptability thresholds: warn_volume=3.2 warn_draft=0.04 warn_speed_balance=2.5 warn_wave=1.1 reject_volume=6.4 reject_draft=0.08 reject_speed_balance=5.0 reject_wave=2.2",
                "hydrostatics": "Hydrostatics-lite: status=ok volume_delta=1.2% draft_delta=0.03 penalty=0.18",
                "calm_water": "Calm-water surrogate: speeds=2 dominant=20.0 aggregate_power=130.5 aggregate_fuel=26.8 aggregate_resistance=4.6 fuel_improvement=1.7% penalty=0.12",
                "wave_response": "Wave-response surrogate: height=1.8 period=7.5 added_resistance=0.42 added_power=18.6 penalty=0.21 status=active",
                "baseline": "Baseline comparison: reference_power=131.1 reference_fuel=27.3 power_improvement=0.5% fuel_improvement=1.7% reference_vs_candidate=stable",
                "multi_condition": "Multi-condition objective: combined_penalty=0.16 dominant=wave_response score=0.19 calm_weight=0.55 wave_weight=0.45",
                "high_fidelity_boundary": "High-fidelity boundary: adapter=openfoam available=no used=no mode=optional",
                "acceptability": "Acceptability: level=ok acceptable=yes hydro=ok operational=ok wave=ok reasons=none",
                "optimization": "Optimization summary: best=cand-1 ranked=3 acceptable=3 warn=0 reject=0 spread=2.0",
                "candidates": "Candidates: cand-1 mid=9.0 | cand-2 mid=8.0 | cand-3 mid=7.0",
                "rejected_candidates": "Rejected candidates: none",
                "optimization_trace": "Optimization trace: 2 comparisons",
                "candidate_rows": [
                    "cand-1 | level=ok | fast=1.0 | mid=9.0 | resistance=4.08 | hydro=0.18 | calm=0.12 | wave=0.21 | reasons=none",
                    "cand-2 | level=ok | fast=0.9 | mid=8.0 | resistance=4.22 | hydro=0.16 | calm=0.14 | wave=0.24 | reasons=none",
                    "cand-3 | level=ok | fast=0.8 | mid=7.0 | resistance=4.35 | hydro=0.14 | calm=0.16 | wave=0.29 | reasons=none",
                ],
                "rejected_candidate_rows": [],
                "optimization_trace_rows": [
                    "cand-1 over cand-2: lower mid_score (resistance=4.08 vs 4.22, hydro=0.18 vs 0.16, calm=0.12 vs 0.14, wave=0.21 vs 0.24)",
                    "cand-2 over cand-3: lower mid_score (resistance=4.22 vs 4.35, hydro=0.16 vs 0.14, calm=0.14 vs 0.16, wave=0.24 vs 0.29)",
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
        operational_profile_summary = central_widget.findChild(QLabel, "operational_profile_summary_label")
        weights_summary = central_widget.findChild(QLabel, "weights_summary_label")
        thresholds_summary = central_widget.findChild(QLabel, "acceptability_thresholds_summary_label")
        hydrostatics_summary = central_widget.findChild(QLabel, "hydrostatics_summary_label")
        calm_water_summary = central_widget.findChild(QLabel, "calm_water_summary_label")
        wave_response_summary = central_widget.findChild(QLabel, "wave_response_summary_label")
        baseline_summary = central_widget.findChild(QLabel, "baseline_summary_label")
        multi_condition_summary = central_widget.findChild(QLabel, "multi_condition_summary_label")
        high_fidelity_boundary_summary = central_widget.findChild(QLabel, "high_fidelity_boundary_summary_label")
        acceptability_summary = central_widget.findChild(QLabel, "acceptability_summary_label")
        optimization_summary = central_widget.findChild(QLabel, "optimization_summary_label")
        candidates_summary = central_widget.findChild(QLabel, "candidates_summary_label")
        rejected_candidates_summary = central_widget.findChild(QLabel, "rejected_candidates_summary_label")
        candidates_list = central_widget.findChild(QListWidget, "candidates_list_widget")
        rejected_candidates_list = central_widget.findChild(QListWidget, "rejected_candidates_list_widget")
        candidates_table = central_widget.findChild(QTableWidget, "candidates_table_widget")
        candidate_filter = central_widget.findChild(QComboBox, "candidate_filter_combo")
        candidate_filter_summary = central_widget.findChild(QLabel, "candidate_filter_summary_label")
        optimization_trace_summary = central_widget.findChild(QLabel, "optimization_trace_summary_label")
        optimization_trace_list = central_widget.findChild(QListWidget, "optimization_trace_list_widget")
        open_case_button = central_widget.findChild(QPushButton, "open_case_button")
        open_report_button = central_widget.findChild(QPushButton, "open_report_button")
        open_best_button = central_widget.findChild(QPushButton, "open_best_candidate_button")

        assert run_button is not None
        assert run_status is not None
        assert artifacts_label is not None
        assert geometry_summary is not None
        assert evaluation_summary is not None
        assert execution_summary is not None
        assert operational_profile_summary is not None
        assert weights_summary is not None
        assert thresholds_summary is not None
        assert hydrostatics_summary is not None
        assert calm_water_summary is not None
        assert wave_response_summary is not None
        assert baseline_summary is not None
        assert multi_condition_summary is not None
        assert high_fidelity_boundary_summary is not None
        assert acceptability_summary is not None
        assert optimization_summary is not None
        assert candidates_summary is not None
        assert rejected_candidates_summary is not None
        assert candidates_list is not None
        assert rejected_candidates_list is not None
        assert candidates_table is not None
        assert candidate_filter is not None
        assert candidate_filter_summary is not None
        assert optimization_trace_summary is not None
        assert optimization_trace_list is not None
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
        assert "source=user_defined" in operational_profile_summary.text()
        assert "weights=0.4,0.6" in operational_profile_summary.text()
        assert "axial=0.8" in weights_summary.text()
        assert "calm=0.55" in weights_summary.text()
        assert "warn_volume=3.2" in thresholds_summary.text()
        assert "reject_speed_balance=5.0" in thresholds_summary.text()
        assert "warn_wave=1.1" in thresholds_summary.text()
        assert "status=ok" in hydrostatics_summary.text()
        assert "volume_delta=1.2%" in hydrostatics_summary.text()
        assert "speeds=2" in calm_water_summary.text()
        assert "dominant=20.0" in calm_water_summary.text()
        assert "aggregate_power=130.5" in calm_water_summary.text()
        assert "aggregate_fuel=26.8" in calm_water_summary.text()
        assert "fuel_improvement=1.7%" in calm_water_summary.text()
        assert "height=1.8" in wave_response_summary.text()
        assert "period=7.5" in wave_response_summary.text()
        assert "added_power=18.6" in wave_response_summary.text()
        assert "reference_power=131.1" in baseline_summary.text()
        assert "reference_fuel=27.3" in baseline_summary.text()
        assert "reference_vs_candidate=stable" in baseline_summary.text()
        assert "dominant=wave_response" in multi_condition_summary.text()
        assert "combined_penalty=0.16" in multi_condition_summary.text()
        assert "adapter=openfoam" in high_fidelity_boundary_summary.text()
        assert "level=ok" in acceptability_summary.text()
        assert "acceptable=yes" in acceptability_summary.text()
        assert "hydro=ok" in acceptability_summary.text()
        assert "wave=ok" in acceptability_summary.text()
        assert "best=cand-1" in optimization_summary.text()
        assert "ranked=3" in optimization_summary.text()
        assert "warn=0" in optimization_summary.text()
        assert "cand-2" in candidates_summary.text()
        assert "cand-3" in candidates_summary.text()
        assert "none" in rejected_candidates_summary.text()
        assert "2 comparisons" in optimization_trace_summary.text()
        assert candidates_list.count() == 3
        assert "cand-2" in candidates_list.item(1).text()
        assert "level=ok" in candidates_list.item(1).text()
        assert "resistance=4.22" in candidates_list.item(1).text()
        assert "wave=0.24" in candidates_list.item(1).text()
        assert rejected_candidates_list.count() == 0
        assert candidates_table.rowCount() == 3
        assert candidates_table.item(1, 0).text() == "cand-2"
        assert candidates_table.item(1, 4).text() == "4.22"
        assert candidates_table.item(1, 7).text() == "0.24"
        assert candidates_table.item(1, 8).text() == "none"
        assert candidates_table.item(0, 1).background().color().name() == QColor("#d9f2d9").name()
        assert "3/3" in candidate_filter_summary.text()
        candidates_table.sortItems(4, Qt.DescendingOrder)
        app.processEvents()
        assert candidates_table.item(0, 0).text() == "cand-3"
        candidates_table.sortItems(4, Qt.AscendingOrder)
        app.processEvents()
        assert candidates_table.item(0, 0).text() == "cand-1"
        candidate_filter.setCurrentText("Rejected")
        app.processEvents()
        assert candidates_table.rowCount() == 0
        assert "0/3" in candidate_filter_summary.text()
        candidate_filter.setCurrentText("Acceptable")
        app.processEvents()
        assert candidates_table.rowCount() == 3
        assert "3/3" in candidate_filter_summary.text()
        candidate_filter.setCurrentText("All")
        app.processEvents()
        assert candidates_table.rowCount() == 3
        assert "3/3" in candidate_filter_summary.text()

        candidate_filter.setCurrentText("Acceptable")
        candidates_table.sortItems(4, Qt.DescendingOrder)
        app.processEvents()
        run_button.click()
        app.processEvents()
        assert candidate_filter.currentText() == "Acceptable"
        assert candidates_table.rowCount() == 3
        assert candidates_table.item(0, 0).text() == "cand-3"
        assert optimization_trace_list.count() == 2
        assert "cand-1 over cand-2" in optimization_trace_list.item(0).text()
        assert "hydro=0.18 vs 0.16" in optimization_trace_list.item(0).text()
        assert "wave=0.21 vs 0.24" in optimization_trace_list.item(0).text()
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
                    "operational_profile": "Operational profile: source=derived_from_speed_knots dominant=20.0 speeds=18.0,20.0 weights=n/a",
                    "weights": "Objective weights: resistance=1.0 axial=0.8 draft=0.1 beam=0.05",
                    "thresholds": "Acceptability thresholds: warn_volume=4.5 warn_draft=0.05 warn_speed_balance=4.0 reject_volume=9.0 reject_draft=0.1 reject_speed_balance=8.0",
                    "hydrostatics": "Hydrostatics-lite: status=warn volume_delta=5.0% draft_delta=0.08 penalty=0.58",
                    "acceptability": "Acceptability: level=warn acceptable=yes hydro=warn operational=ok reasons=hydrostatics_warn",
                    "optimization": "Optimization summary: best=cand-warn ranked=3 acceptable=2 warn=1 reject=1 spread=0.7",
                    "candidates": "Candidates: cand-warn mid=0.5 | cand-2 mid=1.2 | cand-3 mid=1.4",
                    "rejected_candidates": "Rejected candidates: cand-3 reasons=operational_profile_warn",
                    "optimization_trace": "Optimization trace: 2 comparisons",
                    "candidate_rows": [
                        "cand-warn | level=warn | fast=1.0 | mid=0.5 | resistance=4.08 | hydro=0.58 | calm=0.21 | wave=0.12 | reasons=hydrostatics_warn",
                        "cand-2 | level=ok | fast=0.9 | mid=1.2 | resistance=4.12 | hydro=0.11 | calm=0.19 | wave=0.08 | reasons=none",
                        "cand-3 | level=reject | fast=0.8 | mid=1.4 | resistance=4.44 | hydro=0.22 | calm=0.41 | wave=0.36 | reasons=operational_profile_warn",
                    ],
                    "rejected_candidate_rows": [
                        "cand-3 | level=reject | resistance=4.44 | hydro=0.22 | calm=0.41 | wave=0.36 | reasons=operational_profile_warn",
                    ],
                    "optimization_trace_rows": [
                        "cand-warn over cand-2: warn beats ok (resistance=4.08 vs 4.12, hydro=0.58 vs 0.11, calm=0.21 vs 0.19, wave=0.12 vs 0.08)",
                        "cand-2 over cand-3: ok beats reject (resistance=4.12 vs 4.44, hydro=0.11 vs 0.22, calm=0.19 vs 0.41, wave=0.08 vs 0.36)",
                    ],
                    "best_candidate_path": tmp_path / "projects" / "case-301" / "working" / "candidates" / "cand-warn.stl",
                },
        )

        central_widget = window.centralWidget()
        assert central_widget is not None
        run_button = central_widget.findChild(QPushButton, "run_vertical_slice_button")
        run_status = central_widget.findChild(QLabel, "run_status_label")
        hydrostatics_summary = central_widget.findChild(QLabel, "hydrostatics_summary_label")
        acceptability_summary = central_widget.findChild(QLabel, "acceptability_summary_label")
        thresholds_summary = central_widget.findChild(QLabel, "acceptability_thresholds_summary_label")
        rejected_candidates_summary = central_widget.findChild(QLabel, "rejected_candidates_summary_label")
        rejected_candidates_list = central_widget.findChild(QListWidget, "rejected_candidates_list_widget")
        candidates_table = central_widget.findChild(QTableWidget, "candidates_table_widget")
        candidate_filter = central_widget.findChild(QComboBox, "candidate_filter_combo")
        candidate_filter_summary = central_widget.findChild(QLabel, "candidate_filter_summary_label")
        optimization_trace_summary = central_widget.findChild(QLabel, "optimization_trace_summary_label")
        optimization_trace_list = central_widget.findChild(QListWidget, "optimization_trace_list_widget")

        assert run_button is not None
        assert run_status is not None
        assert hydrostatics_summary is not None
        assert acceptability_summary is not None
        assert thresholds_summary is not None
        assert rejected_candidates_summary is not None
        assert rejected_candidates_list is not None
        assert candidates_table is not None
        assert candidate_filter is not None
        assert candidate_filter_summary is not None
        assert optimization_trace_summary is not None
        assert optimization_trace_list is not None

        run_button.click()
        app.processEvents()

        assert "completed_with_warnings" in run_status.text()
        assert "status=warn" in hydrostatics_summary.text()
        assert "level=warn" in acceptability_summary.text()
        assert "acceptable=yes" in acceptability_summary.text()
        assert "warn_volume=4.5" in thresholds_summary.text()
        assert "reject_speed_balance=8.0" in thresholds_summary.text()
        assert "cand-3" in rejected_candidates_summary.text()
        assert rejected_candidates_list.count() == 1
        assert "resistance=4.44" in rejected_candidates_list.item(0).text()
        assert candidates_table.rowCount() == 3
        assert candidates_table.item(0, 7).text() == "0.12"
        assert candidates_table.item(0, 8).text() == "hydrostatics_warn"
        assert candidates_table.item(0, 1).background().color().name() == QColor("#fff1cc").name()
        assert candidates_table.item(2, 1).background().color().name() == QColor("#f4cccc").name()
        assert "3/3" in candidate_filter_summary.text()
        candidate_filter.setCurrentText("Rejected")
        app.processEvents()
        assert candidates_table.rowCount() == 1
        assert candidates_table.item(0, 0).text() == "cand-3"
        assert "1/3" in candidate_filter_summary.text()
        candidate_filter.setCurrentText("Acceptable")
        app.processEvents()
        assert candidates_table.rowCount() == 2
        assert candidates_table.item(0, 0).text() == "cand-warn"
        assert "2/3" in candidate_filter_summary.text()
        candidate_filter.setCurrentText("All")
        app.processEvents()
        assert candidates_table.rowCount() == 3
        assert "3/3" in candidate_filter_summary.text()
        assert "2 comparisons" in optimization_trace_summary.text()
        assert optimization_trace_list.count() == 2
        assert "ok beats reject" in optimization_trace_list.item(1).text()
        assert "calm=0.19 vs 0.41" in optimization_trace_list.item(1).text()
        assert "wave=0.08 vs 0.36" in optimization_trace_list.item(1).text()
    finally:
        window.close()
        app.processEvents()


def test_case_wizard_exposes_optimization_mode_selector(tmp_path: Path, monkeypatch) -> None:
    """Spec §11.3/§11.4: the engineer chooses between generate_new_bulb and
    local_optimize; the wizard's payload must reflect the selection.
    """
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance() or QApplication([])
    wizard = CaseWizard()
    try:
        combo = wizard.findChild(QComboBox, "optimization_mode_combo")
        assert combo is not None
        assert {combo.itemText(i) for i in range(combo.count())} == {
            "generate_new_bulb",
            "local_optimize",
        }
        # Default is generate_new_bulb.
        assert wizard.payload()["optimization_mode"] == "generate_new_bulb"
        # Switch to local_optimize.
        local_index = combo.findText("local_optimize")
        combo.setCurrentIndex(local_index)
        assert wizard.payload()["optimization_mode"] == "local_optimize"
    finally:
        wizard.close()
        app.processEvents()


def test_main_window_resume_button_enabled_only_for_recoverable_cases(
    tmp_path: Path, monkeypatch
) -> None:
    """Spec §10: the desktop should visibly offer continuation, and only for
    cases that actually declare ``is_recoverable=True``.
    """
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    history_summaries = [
        {
            "case_id": "case-completed",
            "case_name": "done",
            "status": "completed",
            "is_recoverable": False,
            "updated_at": "2026-04-18T09:00:00+00:00",
        },
        {
            "case_id": "case-failed",
            "case_name": "failed-run",
            "status": "failed",
            "is_recoverable": True,
            "updated_at": "2026-04-18T10:00:00+00:00",
        },
    ]
    resume_calls: list[str] = []

    def fake_resume(case_id: str):
        resume_calls.append(case_id)
        # Re-mark the case as recovered so history can update.
        for summary in history_summaries:
            if summary["case_id"] == case_id:
                summary["status"] = "completed"
                summary["is_recoverable"] = False
        return CaseSummary(
            case_id=case_id,
            case_name="failed-run",
            status="completed",
            best_candidate_id="cand-1",
        )

    def fake_bootstrap(project_root: Path) -> dict[str, object]:
        return {
            "settings": SimpleNamespace(project_root=project_root),
            "run_vertical_slice": lambda **kwargs: CaseSummary(
                case_id="case-unused",
                case_name=str(kwargs["case_name"]),
                status="completed",
                best_candidate_id="cand-new",
            ),
            "resume_vertical_slice": fake_resume,
            "list_cases": lambda: list(history_summaries),
        }

    monkeypatch.setattr(main_window_module, "bootstrap_application", fake_bootstrap)

    app = QApplication.instance() or QApplication([])
    window = MainWindow(project_root=tmp_path / "projects")
    try:
        central_widget = window.centralWidget()
        assert central_widget is not None

        resume_button = central_widget.findChild(QPushButton, "resume_case_button")
        history_list = central_widget.findChild(QListWidget, "case_history_list_widget")

        assert resume_button is not None
        assert history_list is not None
        assert history_list.count() == 2
        # With nothing selected, resume must be disabled.
        assert resume_button.isEnabled() is False

        # Select the completed case: Resume stays disabled.
        completed_row = next(
            i for i in range(history_list.count()) if "case-completed" in history_list.item(i).text()
        )
        history_list.setCurrentRow(completed_row)
        app.processEvents()
        assert resume_button.isEnabled() is False

        # Select the recoverable case: Resume is enabled.
        failed_row = next(
            i for i in range(history_list.count()) if "case-failed" in history_list.item(i).text()
        )
        history_list.setCurrentRow(failed_row)
        app.processEvents()
        assert resume_button.isEnabled() is True

        (tmp_path / "projects" / "case-failed").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects" / "case-failed" / "artifacts_index.json").write_text("{}", encoding="utf-8")
        resume_button.click()
        app.processEvents()

        assert resume_calls == ["case-failed"]
    finally:
        window.close()
        app.processEvents()


def test_main_window_surfaces_case_history_panel(tmp_path: Path, monkeypatch) -> None:
    """Spec §10 requires the desktop to surface existing cases so engineers can
    pick one for continuation. This smoke test verifies the panel is rendered,
    populated from ``services["list_cases"]``, and refreshed after a new run.
    """
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    call_log: dict[str, int] = {"list_cases_calls": 0}
    history_state: list[list[dict]] = [
        [
            {
                "case_id": "case-earlier",
                "case_name": "earlier",
                "status": "failed",
                "is_recoverable": True,
                "updated_at": "2026-04-18T09:00:00+00:00",
            }
        ]
    ]

    def fake_list_cases() -> list[dict]:
        call_log["list_cases_calls"] += 1
        return history_state[0]

    def fake_runner(**kwargs):
        history_state[0] = history_state[0] + [
            {
                "case_id": "case-new",
                "case_name": str(kwargs["case_name"]),
                "status": "completed",
                "is_recoverable": False,
                "updated_at": "2026-04-18T10:00:00+00:00",
            }
        ]
        return CaseSummary(
            case_id="case-new",
            case_name=str(kwargs["case_name"]),
            status="completed",
            best_candidate_id="cand-1",
        )

    def fake_bootstrap(project_root: Path) -> dict[str, object]:
        return {
            "settings": SimpleNamespace(project_root=project_root),
            "run_vertical_slice": fake_runner,
            "list_cases": fake_list_cases,
        }

    monkeypatch.setattr(main_window_module, "bootstrap_application", fake_bootstrap)

    app = QApplication.instance() or QApplication([])
    window = MainWindow(project_root=tmp_path / "projects")
    try:
        central_widget = window.centralWidget()
        assert central_widget is not None

        history_label = central_widget.findChild(QLabel, "case_history_summary_label")
        history_list = central_widget.findChild(QListWidget, "case_history_list_widget")
        run_button = central_widget.findChild(QPushButton, "run_vertical_slice_button")

        assert history_label is not None
        assert history_list is not None
        assert "recoverable: 1" in history_label.text()
        assert history_list.count() == 1
        assert "case-earlier" in history_list.item(0).text()

        # Stub the artifacts read path so the run doesn't blow up.
        (tmp_path / "projects" / "case-new").mkdir(parents=True, exist_ok=True)
        (tmp_path / "projects" / "case-new" / "artifacts_index.json").write_text("{}", encoding="utf-8")

        # Simulate a run.
        run_button.click()
        app.processEvents()

        assert call_log["list_cases_calls"] >= 2
        assert history_list.count() == 2
        joined_items = "\n".join(history_list.item(i).text() for i in range(history_list.count()))
        assert "case-new" in joined_items
        assert "case-earlier" in joined_items
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
                '"acceptability":{"level":"reject","reasons":["hydrostatics_warn"]},'
                '"geometry_metrics":{"slenderness_ratio":7.2},'
                '"score_components":{"resistance_proxy":0.255}},'
                '{"candidate_id":"candidate-3","fast_score":0.333,"mid_score":7.0,'
                '"acceptability":{"level":"ok","reasons":[]},'
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
        assert "candidate-1" in results["rejected_candidates"]
        assert "runtime=12 h" in results["execution"]
        assert "candidates=5" in results["execution"]
        assert "processed=2" in results["execution"]
        assert len(results["candidate_rows"]) == 2
        assert "candidate-1" in results["candidate_rows"][0]
        assert "level=reject" in results["candidate_rows"][0]
        assert "resistance=0.255" in results["candidate_rows"][0]
        assert len(results["rejected_candidate_rows"]) == 1
        assert results["optimization_trace"] == "Optimization trace: not available"
        assert results["optimization_trace_rows"] == []
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
                '"calm_water":{"speed_count":2,"mean_resistance_proxy":4.2,"mean_power_proxy_kw":120.5,"mean_fuel_proxy_kgph":24.9,"aggregate_resistance_proxy":4.6,"aggregate_power_proxy_kw":130.5,"aggregate_fuel_proxy_kgph":26.8,"reference_aggregate_power_proxy_kw":131.1,"reference_aggregate_fuel_proxy_kgph":27.3,"power_improvement_pct":0.5,"fuel_improvement_pct":1.7,"dominant_speed_knots":20.0,"calm_water_penalty":0.12},'
                '"wave_response":{"wave_height_m":1.8,"wave_period_s":7.5,"added_resistance_proxy":0.42,"added_power_proxy_kw":18.6,"wave_penalty":0.21,"condition_status":"active"},'
                '"operational_profile":{"profile_source":"user_defined","dominant_speed_knots":20.0,"speed_knots":[18.0,20.0],"operational_profile_weights":[0.4,0.6]},'
                '"acceptability_thresholds":{"max_volume_delta_pct":3.2,"max_draft_delta_m":0.04,"max_speed_balance_ratio":2.5,"max_wave_penalty":1.1,"reject_volume_delta_pct":6.4,"reject_draft_delta_m":0.08,"reject_speed_balance_ratio":5.0,"reject_wave_penalty":2.2},'
                '"acceptability":{"is_acceptable":true,"level":"ok","hydrostatics_status":"ok","operational_profile_status":"ok","wave_response_status":"ok","reasons":[]},'
                '"execution":{"runtime_budget_hours":7,"candidate_count":4,"processed_candidates":4},'
                '"objective_weights":{"resistance_weight":1.1,"axial_gain_weight":0.3,"draft_reduction_weight":0.05,"beam_growth_weight":0.2,"calm_water_condition_weight":0.55,"wave_condition_weight":0.45},'
                '"multi_condition_objective":{"combined_penalty":0.16,"combined_objective_score":0.19,"dominant_condition":"wave_response","calm_water_weight":0.55,"wave_response_weight":0.45},'
                '"optimization":{"best_candidate_id":"candidate-9","ranked_count":4,"acceptable_count":4,"warn_count":0,"reject_count":1,"mid_score_spread":0.8},'
                '"optimization_trace":{"summary":"Optimization trace: 1 comparison","rows":["candidate-9 over candidate-7: ok beats reject (resistance=3.14 vs 3.44, hydro=0.15 vs 0.35, calm=0.12 vs 0.42)"]},'
                '"candidates":{"summary":"Candidates: candidate-9 mid=1.5 | candidate-7 mid=2.3","rows":["candidate-9 | level=ok | fast=0.2 | mid=1.5 | resistance=3.14 | hydro=0.15 | calm=0.12 | reasons=none","candidate-7 | level=reject | fast=0.3 | mid=2.3 | resistance=3.44 | hydro=0.35 | calm=0.42 | reasons=hydrostatics_warn"]},'
                '"rejected_candidates":{"summary":"Rejected candidates: candidate-7 reasons=hydrostatics_warn","rows":["candidate-7 | level=reject | resistance=3.44 | hydro=0.35 | calm=0.42 | reasons=hydrostatics_warn"]}'
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
        assert "source=user_defined" in results["operational_profile"]
        assert "weights=0.4,0.6" in results["operational_profile"]
        assert "warn_volume=3.2" in results["thresholds"]
        assert "reject_volume=6.4" in results["thresholds"]
        assert "reject_speed_balance=5.0" in results["thresholds"]
        assert "warn_wave=1.1" in results["thresholds"]
        assert "level=ok" in results["acceptability"]
        assert "acceptable=yes" in results["acceptability"]
        assert "wave=ok" in results["acceptability"]
        assert "resistance=1.1" in results["weights"]
        assert "beam=0.2" in results["weights"]
        assert "calm=0.55" in results["weights"]
        assert "status=ok" in results["hydrostatics"]
        assert "volume_delta=1.1%" in results["hydrostatics"]
        assert "penalty=0.15" in results["hydrostatics"]
        assert "speeds=2" in results["calm_water"]
        assert "dominant=20.0" in results["calm_water"]
        assert "aggregate_power=130.5" in results["calm_water"]
        assert "aggregate_fuel=26.8" in results["calm_water"]
        assert "fuel_improvement=1.7%" in results["calm_water"]
        assert "height=1.8" in results["wave_response"]
        assert "period=7.5" in results["wave_response"]
        assert "added_resistance=0.42" in results["wave_response"]
        assert "reference_power=131.1" in results["baseline"]
        assert "reference_fuel=27.3" in results["baseline"]
        assert "power_improvement=0.5%" in results["baseline"]
        assert "fuel_improvement=1.7%" in results["baseline"]
        assert "combined_penalty=0.16" in results["multi_condition"]
        assert "dominant=wave_response" in results["multi_condition"]
        assert "best=candidate-9" in results["optimization"]
        assert "ranked=4" in results["optimization"]
        assert "warn=0" in results["optimization"]
        assert "spread=0.8" in results["optimization"]
        assert "candidate-7" in results["candidates"]
        assert "candidate-7" in results["rejected_candidates"]
        assert len(results["candidate_rows"]) == 2
        assert "level=reject" in results["candidate_rows"][1]
        assert "resistance=3.44" in results["candidate_rows"][1]
        assert len(results["rejected_candidate_rows"]) == 1
        assert "1 comparison" in results["optimization_trace"]
        assert len(results["optimization_trace_rows"]) == 1
        assert "hydro=0.15 vs 0.35" in results["optimization_trace_rows"][0]
    finally:
        window.close()
        app.processEvents()
