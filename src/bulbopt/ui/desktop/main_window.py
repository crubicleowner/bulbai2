from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QBrush, QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bulbopt.app.bootstrap import bootstrap_application
from bulbopt.storage.filesystem.json_store import JsonStore
from bulbopt.ui.desktop.case_wizard import CaseWizard


class MainWindow(QMainWindow):
    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BulbOpt Desktop")
        self.services = bootstrap_application(project_root=project_root)
        self._case_wizard: CaseWizard | None = None
        self._run_status_label: QLabel | None = None
        self._artifacts_label: QLabel | None = None
        self._geometry_summary_label: QLabel | None = None
        self._evaluation_summary_label: QLabel | None = None
        self._execution_summary_label: QLabel | None = None
        self._operational_profile_summary_label: QLabel | None = None
        self._weights_summary_label: QLabel | None = None
        self._acceptability_thresholds_summary_label: QLabel | None = None
        self._hydrostatics_summary_label: QLabel | None = None
        self._calm_water_summary_label: QLabel | None = None
        self._wave_response_summary_label: QLabel | None = None
        self._baseline_summary_label: QLabel | None = None
        self._multi_condition_summary_label: QLabel | None = None
        self._high_fidelity_boundary_summary_label: QLabel | None = None
        self._acceptability_summary_label: QLabel | None = None
        self._optimization_summary_label: QLabel | None = None
        self._candidates_summary_label: QLabel | None = None
        self._rejected_candidates_summary_label: QLabel | None = None
        self._candidates_list_widget: QListWidget | None = None
        self._candidates_table_widget: QTableWidget | None = None
        self._candidate_filter_combo: QComboBox | None = None
        self._candidate_filter_summary_label: QLabel | None = None
        self._rejected_candidates_list_widget: QListWidget | None = None
        self._optimization_trace_summary_label: QLabel | None = None
        self._optimization_trace_list_widget: QListWidget | None = None
        self._open_case_button: QPushButton | None = None
        self._open_report_button: QPushButton | None = None
        self._open_best_candidate_button: QPushButton | None = None
        self._case_history_summary_label: QLabel | None = None
        self._case_history_list_widget: QListWidget | None = None
        self._resume_case_button: QPushButton | None = None
        self._detect_bulb_region_button: QPushButton | None = None
        self._bulb_region_preview_label: QLabel | None = None
        self._last_case_dir: Path | None = None
        self._last_report_path: Path | None = None
        self._last_best_candidate_path: Path | None = None
        self._candidate_rows_all: list[str] = []
        self._current_sort_column: int = -1
        self._current_sort_order: Qt.SortOrder = Qt.AscendingOrder
        self._json_store = JsonStore()
        self._build_central_widget()

    def _build_central_widget(self) -> None:
        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)

        app_label = QLabel("BulbOpt Desktop", central_widget)
        app_label.setObjectName("app_name_label")
        ready_label = QLabel("Ready for STL-first vertical slice", central_widget)
        ready_label.setObjectName("ready_state_label")
        self._case_wizard = CaseWizard(central_widget)

        self._detect_bulb_region_button = QPushButton("Detect Bulb Region", central_widget)
        self._detect_bulb_region_button.setObjectName("detect_bulb_region_button")
        self._detect_bulb_region_button.clicked.connect(self._detect_bulb_region)
        self._bulb_region_preview_label = QLabel(
            "Bulb region preview: not detected yet",
            central_widget,
        )
        self._bulb_region_preview_label.setObjectName("bulb_region_preview_label")

        run_button = QPushButton("Run Vertical Slice", central_widget)
        run_button.setObjectName("run_vertical_slice_button")
        run_button.clicked.connect(self._run_vertical_slice)

        self._run_status_label = QLabel("Idle: ready to execute demo case", central_widget)
        self._run_status_label.setObjectName("run_status_label")
        results_label = QLabel("Results", central_widget)
        results_label.setObjectName("results_panel_label")
        self._artifacts_label = QLabel("No artifacts yet", central_widget)
        self._artifacts_label.setObjectName("artifacts_label")
        self._geometry_summary_label = QLabel(
            "Geometry summary: not available",
            central_widget,
        )
        self._geometry_summary_label.setObjectName("geometry_summary_label")
        self._evaluation_summary_label = QLabel(
            "Evaluation summary: not available",
            central_widget,
        )
        self._evaluation_summary_label.setObjectName("evaluation_summary_label")
        self._execution_summary_label = QLabel(
            "Execution summary: not available",
            central_widget,
        )
        self._execution_summary_label.setObjectName("execution_summary_label")
        self._operational_profile_summary_label = QLabel(
            "Operational profile: not available",
            central_widget,
        )
        self._operational_profile_summary_label.setObjectName("operational_profile_summary_label")
        self._weights_summary_label = QLabel(
            "Objective weights: not available",
            central_widget,
        )
        self._weights_summary_label.setObjectName("weights_summary_label")
        self._acceptability_thresholds_summary_label = QLabel(
            "Acceptability thresholds: not available",
            central_widget,
        )
        self._acceptability_thresholds_summary_label.setObjectName("acceptability_thresholds_summary_label")
        self._hydrostatics_summary_label = QLabel(
            "Hydrostatics-lite: not available",
            central_widget,
        )
        self._hydrostatics_summary_label.setObjectName("hydrostatics_summary_label")
        self._calm_water_summary_label = QLabel(
            "Calm-water surrogate: not available",
            central_widget,
        )
        self._calm_water_summary_label.setObjectName("calm_water_summary_label")
        self._wave_response_summary_label = QLabel(
            "Wave-response surrogate: not available",
            central_widget,
        )
        self._wave_response_summary_label.setObjectName("wave_response_summary_label")
        self._baseline_summary_label = QLabel(
            "Baseline comparison: not available",
            central_widget,
        )
        self._baseline_summary_label.setObjectName("baseline_summary_label")
        self._multi_condition_summary_label = QLabel(
            "Multi-condition objective: not available",
            central_widget,
        )
        self._multi_condition_summary_label.setObjectName("multi_condition_summary_label")
        self._high_fidelity_boundary_summary_label = QLabel(
            "High-fidelity boundary: not available",
            central_widget,
        )
        self._high_fidelity_boundary_summary_label.setObjectName("high_fidelity_boundary_summary_label")
        self._acceptability_summary_label = QLabel(
            "Acceptability: not available",
            central_widget,
        )
        self._acceptability_summary_label.setObjectName("acceptability_summary_label")
        self._optimization_summary_label = QLabel(
            "Optimization summary: not available",
            central_widget,
        )
        self._optimization_summary_label.setObjectName("optimization_summary_label")
        self._candidates_summary_label = QLabel(
            "Candidates summary: not available",
            central_widget,
        )
        self._candidates_summary_label.setObjectName("candidates_summary_label")
        self._rejected_candidates_summary_label = QLabel(
            "Rejected candidates: not available",
            central_widget,
        )
        self._rejected_candidates_summary_label.setObjectName("rejected_candidates_summary_label")
        self._candidates_list_widget = QListWidget(central_widget)
        self._candidates_list_widget.setObjectName("candidates_list_widget")
        self._candidate_filter_combo = QComboBox(central_widget)
        self._candidate_filter_combo.setObjectName("candidate_filter_combo")
        self._candidate_filter_combo.addItems(["All", "Acceptable", "Rejected"])
        self._candidate_filter_combo.currentTextChanged.connect(self._apply_candidate_filter)
        self._candidate_filter_summary_label = QLabel("Candidates shown: 0/0", central_widget)
        self._candidate_filter_summary_label.setObjectName("candidate_filter_summary_label")
        self._candidates_table_widget = QTableWidget(0, 9, central_widget)
        self._candidates_table_widget.setObjectName("candidates_table_widget")
        self._candidates_table_widget.setHorizontalHeaderLabels(
            ["Candidate", "Level", "Fast", "Mid", "Resistance", "Hydro", "Calm", "Wave", "Reasons"]
        )
        self._candidates_table_widget.setSortingEnabled(True)
        self._candidates_table_widget.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self._candidates_table_widget.horizontalHeader().sortIndicatorChanged.connect(self._remember_sort_state)
        self._rejected_candidates_list_widget = QListWidget(central_widget)
        self._rejected_candidates_list_widget.setObjectName("rejected_candidates_list_widget")
        self._optimization_trace_summary_label = QLabel(
            "Optimization trace: not available",
            central_widget,
        )
        self._optimization_trace_summary_label.setObjectName("optimization_trace_summary_label")
        self._optimization_trace_list_widget = QListWidget(central_widget)
        self._optimization_trace_list_widget.setObjectName("optimization_trace_list_widget")
        self._case_history_summary_label = QLabel("Previous cases: none yet", central_widget)
        self._case_history_summary_label.setObjectName("case_history_summary_label")
        self._case_history_list_widget = QListWidget(central_widget)
        self._case_history_list_widget.setObjectName("case_history_list_widget")
        self._case_history_list_widget.currentItemChanged.connect(lambda *_: self._update_resume_button_state())
        self._resume_case_button = QPushButton("Resume Selected Case", central_widget)
        self._resume_case_button.setObjectName("resume_case_button")
        self._resume_case_button.setEnabled(False)
        self._resume_case_button.clicked.connect(self._resume_selected_case)
        self._open_case_button = QPushButton("Open Case Folder", central_widget)
        self._open_case_button.setObjectName("open_case_button")
        self._open_case_button.setEnabled(False)
        self._open_case_button.clicked.connect(self._open_case_dir)
        self._open_report_button = QPushButton("Open Report", central_widget)
        self._open_report_button.setObjectName("open_report_button")
        self._open_report_button.setEnabled(False)
        self._open_report_button.clicked.connect(self._open_report)
        self._open_best_candidate_button = QPushButton("Open Best Candidate STL", central_widget)
        self._open_best_candidate_button.setObjectName("open_best_candidate_button")
        self._open_best_candidate_button.setEnabled(False)
        self._open_best_candidate_button.clicked.connect(self._open_best_candidate)

        layout.addWidget(app_label)
        layout.addWidget(ready_label)
        layout.addWidget(self._case_wizard)
        layout.addWidget(self._detect_bulb_region_button)
        layout.addWidget(self._bulb_region_preview_label)
        layout.addWidget(run_button)
        layout.addWidget(self._run_status_label)
        layout.addWidget(results_label)
        layout.addWidget(self._artifacts_label)
        layout.addWidget(self._geometry_summary_label)
        layout.addWidget(self._evaluation_summary_label)
        layout.addWidget(self._execution_summary_label)
        layout.addWidget(self._operational_profile_summary_label)
        layout.addWidget(self._weights_summary_label)
        layout.addWidget(self._acceptability_thresholds_summary_label)
        layout.addWidget(self._hydrostatics_summary_label)
        layout.addWidget(self._calm_water_summary_label)
        layout.addWidget(self._wave_response_summary_label)
        layout.addWidget(self._baseline_summary_label)
        layout.addWidget(self._multi_condition_summary_label)
        layout.addWidget(self._high_fidelity_boundary_summary_label)
        layout.addWidget(self._acceptability_summary_label)
        layout.addWidget(self._optimization_summary_label)
        layout.addWidget(self._candidates_summary_label)
        layout.addWidget(self._rejected_candidates_summary_label)
        layout.addWidget(self._candidates_list_widget)
        layout.addWidget(self._candidate_filter_combo)
        layout.addWidget(self._candidate_filter_summary_label)
        layout.addWidget(self._candidates_table_widget)
        layout.addWidget(self._rejected_candidates_list_widget)
        layout.addWidget(self._optimization_trace_summary_label)
        layout.addWidget(self._optimization_trace_list_widget)
        layout.addWidget(self._case_history_summary_label)
        layout.addWidget(self._case_history_list_widget)
        layout.addWidget(self._resume_case_button)
        layout.addWidget(self._open_case_button)
        layout.addWidget(self._open_report_button)
        layout.addWidget(self._open_best_candidate_button)
        layout.addStretch(1)

        self.setCentralWidget(central_widget)
        self._refresh_case_history()

    def _run_vertical_slice(self) -> None:
        if (
            self._case_wizard is None
            or self._run_status_label is None
            or self._artifacts_label is None
            or self._geometry_summary_label is None
            or self._evaluation_summary_label is None
            or self._execution_summary_label is None
            or self._operational_profile_summary_label is None
            or self._weights_summary_label is None
            or self._acceptability_thresholds_summary_label is None
            or self._hydrostatics_summary_label is None
            or self._calm_water_summary_label is None
            or self._wave_response_summary_label is None
            or self._baseline_summary_label is None
            or self._multi_condition_summary_label is None
            or self._high_fidelity_boundary_summary_label is None
            or self._acceptability_summary_label is None
            or self._optimization_summary_label is None
            or self._candidates_summary_label is None
            or self._rejected_candidates_summary_label is None
            or self._candidates_list_widget is None
            or self._candidates_table_widget is None
            or self._candidate_filter_combo is None
            or self._candidate_filter_summary_label is None
            or self._rejected_candidates_list_widget is None
            or self._optimization_trace_summary_label is None
            or self._optimization_trace_list_widget is None
            or self._open_case_button is None
            or self._open_report_button is None
            or self._open_best_candidate_button is None
        ):
            return

        payload = self._case_wizard.payload()
        self._run_status_label.setText("Running vertical slice...")
        self._last_case_dir = None
        self._last_report_path = None
        self._last_best_candidate_path = None
        self._open_case_button.setEnabled(False)
        self._open_report_button.setEnabled(False)
        self._open_best_candidate_button.setEnabled(False)
        self._geometry_summary_label.setText("Geometry summary: not available")
        self._evaluation_summary_label.setText("Evaluation summary: not available")
        self._execution_summary_label.setText("Execution summary: not available")
        self._operational_profile_summary_label.setText("Operational profile: not available")
        self._weights_summary_label.setText("Objective weights: not available")
        self._acceptability_thresholds_summary_label.setText("Acceptability thresholds: not available")
        self._hydrostatics_summary_label.setText("Hydrostatics-lite: not available")
        self._calm_water_summary_label.setText("Calm-water surrogate: not available")
        self._wave_response_summary_label.setText("Wave-response surrogate: not available")
        self._baseline_summary_label.setText("Baseline comparison: not available")
        self._multi_condition_summary_label.setText("Multi-condition objective: not available")
        self._high_fidelity_boundary_summary_label.setText("High-fidelity boundary: not available")
        self._acceptability_summary_label.setText("Acceptability: not available")
        self._optimization_summary_label.setText("Optimization summary: not available")
        self._candidates_summary_label.setText("Candidates summary: not available")
        self._rejected_candidates_summary_label.setText("Rejected candidates: not available")
        self._optimization_trace_summary_label.setText("Optimization trace: not available")
        self._candidate_rows_all = []
        self._candidates_list_widget.clear()
        self._candidates_table_widget.setRowCount(0)
        self._candidate_filter_summary_label.setText("Candidates shown: 0/0")
        self._rejected_candidates_list_widget.clear()
        self._optimization_trace_list_widget.clear()

        try:
            summary = self.services["run_vertical_slice"](**payload)
        except Exception as error:
            self._run_status_label.setText(f"Failed: {error}")
            self._artifacts_label.setText("Artifacts unavailable because execution failed")
            return

        project_root = self.services["settings"].project_root
        self._last_case_dir = project_root / summary.case_id
        self._last_report_path = self._last_case_dir / "outputs" / "reports" / "report.html"
        status_label = summary.status
        if summary.status == "completed":
            status_label = "Completed"
        self._run_status_label.setText(
            f"{status_label}: "
            f"{summary.case_id} | best candidate {summary.best_candidate_id or 'n/a'}"
        )
        self._artifacts_label.setText(
            f"Case: {self._last_case_dir} | Report: {self._last_report_path}"
        )
        results_payload = self._load_case_results(self._last_case_dir, summary.best_candidate_id)
        self._last_best_candidate_path = results_payload.get("best_candidate_path")
        self._geometry_summary_label.setText(str(results_payload.get("geometry", "Geometry summary: not available")))
        self._evaluation_summary_label.setText(str(results_payload.get("evaluation", "Evaluation summary: not available")))
        self._execution_summary_label.setText(str(results_payload.get("execution", "Execution summary: not available")))
        self._operational_profile_summary_label.setText(
            str(results_payload.get("operational_profile", "Operational profile: not available"))
        )
        self._weights_summary_label.setText(str(results_payload.get("weights", "Objective weights: not available")))
        self._acceptability_thresholds_summary_label.setText(
            str(results_payload.get("thresholds", "Acceptability thresholds: not available"))
        )
        self._hydrostatics_summary_label.setText(str(results_payload.get("hydrostatics", "Hydrostatics-lite: not available")))
        self._calm_water_summary_label.setText(str(results_payload.get("calm_water", "Calm-water surrogate: not available")))
        self._wave_response_summary_label.setText(
            str(results_payload.get("wave_response", "Wave-response surrogate: not available"))
        )
        self._baseline_summary_label.setText(str(results_payload.get("baseline", "Baseline comparison: not available")))
        self._multi_condition_summary_label.setText(
            str(results_payload.get("multi_condition", "Multi-condition objective: not available"))
        )
        self._high_fidelity_boundary_summary_label.setText(
            str(results_payload.get("high_fidelity_boundary", "High-fidelity boundary: not available"))
        )
        self._acceptability_summary_label.setText(str(results_payload.get("acceptability", "Acceptability: not available")))
        self._optimization_summary_label.setText(str(results_payload.get("optimization", "Optimization summary: not available")))
        self._candidates_summary_label.setText(str(results_payload.get("candidates", "Candidates summary: not available")))
        self._rejected_candidates_summary_label.setText(
            str(results_payload.get("rejected_candidates", "Rejected candidates: not available"))
        )
        self._optimization_trace_summary_label.setText(
            str(results_payload.get("optimization_trace", "Optimization trace: not available"))
        )
        self._candidate_rows_all = list(results_payload.get("candidate_rows", []))
        self._candidates_list_widget.addItems(self._candidate_rows_all)
        self._apply_candidate_filter(self._candidate_filter_combo.currentText())
        self._rejected_candidates_list_widget.addItems(list(results_payload.get("rejected_candidate_rows", [])))
        self._optimization_trace_list_widget.addItems(list(results_payload.get("optimization_trace_rows", [])))
        self._open_case_button.setEnabled(True)
        self._open_report_button.setEnabled(True)
        self._open_best_candidate_button.setEnabled(self._last_best_candidate_path is not None)
        self._refresh_case_history()

    def _detect_bulb_region(self) -> None:
        """Run the detect-only geometry preview so the engineer can review
        the auto-detected axis_min/axis_max before committing to a full run
        (spec §11.2).
        """
        if self._case_wizard is None or self._bulb_region_preview_label is None:
            return
        detect = self.services.get("detect_bulb_region")
        if not callable(detect):
            self._bulb_region_preview_label.setText("Detect Bulb Region: service not available")
            return

        payload = self._case_wizard.payload()
        source_path = str(payload.get("source_path") or "")
        if not source_path:
            self._bulb_region_preview_label.setText(
                "Detect Bulb Region: please select a source STL first"
            )
            return

        try:
            preview = detect(source_path)
        except Exception as error:
            self._bulb_region_preview_label.setText(f"Detect Bulb Region failed: {error}")
            return

        bulb_region = preview.get("bulb_region", {})
        quality_report = preview.get("quality_report", {})
        self._bulb_region_preview_label.setText(
            "Bulb region preview: "
            f"axis={bulb_region.get('axis_index', 'n/a')} "
            f"auto_min={bulb_region.get('auto_axis_min', 'n/a')} "
            f"auto_max={bulb_region.get('auto_axis_max', 'n/a')} "
            f"mask_ratio={bulb_region.get('mask_ratio', 'n/a')} "
            f"watertight={quality_report.get('watertight', 'n/a')}"
        )

    def _refresh_case_history(self) -> None:
        """Populate the case history panel from the repository (spec §10)."""
        if self._case_history_list_widget is None or self._case_history_summary_label is None:
            return

        list_cases = self.services.get("list_cases")
        if not callable(list_cases):
            return

        summaries = list_cases()
        self._case_history_list_widget.clear()
        if not summaries:
            self._case_history_summary_label.setText("Previous cases: none yet")
            self._update_resume_button_state()
            return

        recoverable_count = sum(1 for summary in summaries if summary.get("is_recoverable"))
        self._case_history_summary_label.setText(
            f"Previous cases: {len(summaries)} total | recoverable: {recoverable_count}"
        )
        for summary in summaries:
            recoverable_flag = " (recoverable)" if summary.get("is_recoverable") else ""
            from PySide6.QtWidgets import QListWidgetItem
            from PySide6.QtCore import Qt

            item = QListWidgetItem(
                f"{summary.get('case_id', 'n/a')} | "
                f"{summary.get('case_name', 'n/a')} | "
                f"status={summary.get('status', 'n/a')}{recoverable_flag} | "
                f"updated={summary.get('updated_at', 'n/a')}"
            )
            # Store case metadata on the item so Resume can look it up without reparsing text.
            item.setData(Qt.UserRole, dict(summary))
            self._case_history_list_widget.addItem(item)

        self._update_resume_button_state()

    def _update_resume_button_state(self) -> None:
        if self._resume_case_button is None or self._case_history_list_widget is None:
            return
        current_item = self._case_history_list_widget.currentItem()
        if current_item is None:
            self._resume_case_button.setEnabled(False)
            return
        from PySide6.QtCore import Qt

        summary = current_item.data(Qt.UserRole) or {}
        self._resume_case_button.setEnabled(bool(summary.get("is_recoverable")))

    def _resume_selected_case(self) -> None:
        if (
            self._case_history_list_widget is None
            or self._run_status_label is None
            or self._resume_case_button is None
        ):
            return
        resume = self.services.get("resume_vertical_slice")
        if not callable(resume):
            return
        current_item = self._case_history_list_widget.currentItem()
        if current_item is None:
            return
        from PySide6.QtCore import Qt

        summary_payload = current_item.data(Qt.UserRole) or {}
        case_id = summary_payload.get("case_id")
        if not case_id:
            return
        self._run_status_label.setText(f"Resuming {case_id}...")
        try:
            summary = resume(case_id)
        except Exception as error:
            self._run_status_label.setText(f"Resume failed: {error}")
            self._refresh_case_history()
            return

        project_root = self.services["settings"].project_root
        self._last_case_dir = project_root / summary.case_id
        self._last_report_path = self._last_case_dir / "outputs" / "reports" / "report.html"
        status_label = summary.status if summary.status else "Resumed"
        self._run_status_label.setText(
            f"Resume {status_label}: {summary.case_id} | best {summary.best_candidate_id or 'n/a'}"
        )
        if self._open_case_button is not None:
            self._open_case_button.setEnabled(True)
        if self._open_report_button is not None:
            self._open_report_button.setEnabled(True)
        self._refresh_case_history()

    def _open_case_dir(self) -> None:
        if self._last_case_dir is not None:
            self._open_path(self._last_case_dir)

    def _open_report(self) -> None:
        if self._last_report_path is not None:
            self._open_path(self._last_report_path)

    def _open_best_candidate(self) -> None:
        if self._last_best_candidate_path is not None:
            self._open_path(self._last_best_candidate_path)

    def _open_path(self, path: Path) -> bool:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _load_case_results(self, case_dir: Path, best_candidate_id: str | None) -> dict[str, str | Path | None | list[str]]:
        geometry_summary = "Geometry summary: not available"
        evaluation_summary = "Evaluation summary: not available"
        execution_summary = "Execution summary: not available"
        operational_profile_summary = "Operational profile: not available"
        weights_summary = "Objective weights: not available"
        thresholds_summary = "Acceptability thresholds: not available"
        hydrostatics_summary = "Hydrostatics-lite: not available"
        calm_water_summary = "Calm-water surrogate: not available"
        wave_response_summary = "Wave-response surrogate: not available"
        baseline_summary = "Baseline comparison: not available"
        multi_condition_summary = "Multi-condition objective: not available"
        high_fidelity_boundary_summary = "High-fidelity boundary: not available"
        acceptability_summary = "Acceptability: not available"
        optimization_summary = "Optimization summary: not available"
        candidates_summary = "Candidates summary: not available"
        rejected_candidates_summary = "Rejected candidates: not available"
        optimization_trace_summary = "Optimization trace: not available"
        candidate_rows: list[str] = []
        rejected_candidate_rows: list[str] = []
        optimization_trace_rows: list[str] = []
        best_candidate_path: Path | None = None
        quality_report: dict = {}

        case_path = case_dir / "case.json"
        geometry_path = case_dir / "working" / "repaired" / "geometry_analysis.json"
        evaluation_path = case_dir / "evaluation_index.json"
        metadata_path = case_dir / "metadata.json"
        optimization_path = case_dir / "working" / "evaluation" / "optimization_summary.json"
        artifacts_path = case_dir / "artifacts_index.json"

        if case_path.exists():
            case_payload = self._json_store.read(case_path)
            summary_metrics = case_payload.get("summary_metrics", {})
            if summary_metrics:
                summary_results = self._build_results_from_case_summary(summary_metrics)
                geometry_summary = summary_results["geometry"]
                evaluation_summary = summary_results["evaluation"]
                execution_summary = summary_results["execution"]
                operational_profile_summary = summary_results["operational_profile"]
                weights_summary = summary_results["weights"]
                thresholds_summary = summary_results["thresholds"]
                hydrostatics_summary = summary_results["hydrostatics"]
                calm_water_summary = summary_results["calm_water"]
                wave_response_summary = summary_results.get("wave_response", wave_response_summary)
                baseline_summary = summary_results.get("baseline", baseline_summary)
                multi_condition_summary = summary_results.get("multi_condition", multi_condition_summary)
                high_fidelity_boundary_summary = summary_results.get(
                    "high_fidelity_boundary",
                    high_fidelity_boundary_summary,
                )
                acceptability_summary = summary_results["acceptability"]
                optimization_summary = summary_results["optimization"]
                candidates_summary = summary_results["candidates"]
                rejected_candidates_summary = summary_results["rejected_candidates"]
                optimization_trace_summary = summary_results["optimization_trace"]
                candidate_rows = summary_results["candidate_rows"]
                rejected_candidate_rows = summary_results["rejected_candidate_rows"]
                optimization_trace_rows = summary_results["optimization_trace_rows"]
                best_candidate_path = summary_results["best_candidate_path"]

        if geometry_path.exists():
            geometry_payload = self._json_store.read(geometry_path)
            quality_report = geometry_payload.get("quality_report", {})
            geometry_summary = self._format_geometry_summary(quality_report)

        if evaluation_path.exists():
            evaluation_payload = self._json_store.read(evaluation_path)
            ranked_candidates = []
            for item in evaluation_payload:
                candidate_row = (
                    f"{item.get('candidate_id', 'n/a')} | "
                    f"level={item.get('acceptability', {}).get('level', 'n/a')} | "
                    f"fast={item.get('fast_score', 'n/a')} | "
                    f"mid={item.get('mid_score', 'n/a')} | "
                    f"resistance={item.get('score_components', {}).get('resistance_proxy', 'n/a')} | "
                    f"hydro={item.get('score_components', {}).get('hydrostatic_penalty', 'n/a')} | "
                    f"calm={item.get('score_components', {}).get('calm_water_penalty', 'n/a')} | "
                    f"wave={item.get('score_components', {}).get('wave_penalty', 'n/a')} | "
                    f"reasons={','.join(item.get('acceptability', {}).get('reasons', [])) or 'none'}"
                )
                candidate_rows.append(candidate_row)
                ranked_candidates.append(f"{item.get('candidate_id', 'n/a')} mid={item.get('mid_score', 'n/a')}")
            if ranked_candidates:
                candidates_summary = "Candidates: " + " | ".join(ranked_candidates)
            rejected_candidates = [
                item for item in evaluation_payload if item.get("acceptability", {}).get("level") == "reject"
            ]
            if rejected_candidates:
                rejected_candidate_rows = [
                    (
                        f"{item.get('candidate_id', 'n/a')} | "
                        f"level=reject | "
                        f"resistance={item.get('score_components', {}).get('resistance_proxy', 'n/a')} | "
                        f"hydro={item.get('score_components', {}).get('hydrostatic_penalty', 'n/a')} | "
                        f"calm={item.get('score_components', {}).get('calm_water_penalty', 'n/a')} | "
                        f"wave={item.get('score_components', {}).get('wave_penalty', 'n/a')} | "
                        f"reasons={','.join(item.get('acceptability', {}).get('reasons', [])) or 'none'}"
                    )
                    for item in rejected_candidates
                ]
                rejected_candidates_summary = "Rejected candidates: " + " | ".join(
                    f"{item.get('candidate_id', 'n/a')} reasons={','.join(item.get('acceptability', {}).get('reasons', [])) or 'none'}"
                    for item in rejected_candidates
                )
            else:
                rejected_candidates_summary = "Rejected candidates: none"
            optimization_trace_summary = "Optimization trace: not available"
            optimization_trace_rows = []

            best_candidate = next(
                (
                    item
                    for item in evaluation_payload
                    if item.get("candidate_id") == best_candidate_id
                ),
                evaluation_payload[0] if evaluation_payload else None,
            )
            if best_candidate is not None:
                geometry_metrics = best_candidate.get("geometry_metrics", {})
                score_components = best_candidate.get("score_components", {})
                geometry_summary = self._format_geometry_summary(
                    {
                        **quality_report,
                        "slenderness_ratio": geometry_metrics.get("slenderness_ratio", "n/a"),
                    }
                )
                evaluation_summary = self._format_evaluation_summary(
                    {
                        "best_candidate_id": best_candidate.get("candidate_id", "n/a"),
                        "fast_score": best_candidate.get("fast_score", "n/a"),
                        "mid_score": best_candidate.get("mid_score", "n/a"),
                        "resistance_proxy": score_components.get("resistance_proxy", "n/a"),
                    }
                )
                hydrostatics_summary = self._format_hydrostatics_summary(
                    {
                        "volume_delta_pct": best_candidate.get("hydrostatics_metrics", {}).get("volume_delta_pct", "n/a"),
                        "draft_delta_m": best_candidate.get("hydrostatics_metrics", {}).get("draft_delta_m", "n/a"),
                        "hydrostatic_penalty": score_components.get("hydrostatic_penalty", "n/a"),
                    }
                )
                calm_water_summary = self._format_calm_water_summary(
                    {
                        "speed_count": best_candidate.get("calm_water_metrics", {}).get("speed_count", "n/a"),
                        "mean_resistance_proxy": best_candidate.get("calm_water_metrics", {}).get(
                            "mean_resistance_proxy", "n/a"
                        ),
                        "mean_power_proxy_kw": best_candidate.get("calm_water_metrics", {}).get(
                            "mean_power_proxy_kw", "n/a"
                        ),
                        "aggregate_resistance_proxy": best_candidate.get("calm_water_metrics", {}).get(
                            "aggregate_resistance_proxy", "n/a"
                        ),
                        "aggregate_power_proxy_kw": best_candidate.get("calm_water_metrics", {}).get(
                            "aggregate_power_proxy_kw", "n/a"
                        ),
                        "dominant_speed_knots": best_candidate.get("calm_water_metrics", {}).get(
                            "dominant_speed_knots", "n/a"
                        ),
                        "calm_water_penalty": score_components.get("calm_water_penalty", "n/a"),
                    }
                )
                baseline_summary = self._format_baseline_summary(
                    {
                        "reference_aggregate_power_proxy_kw": best_candidate.get("calm_water_metrics", {}).get(
                            "reference_aggregate_power_proxy_kw",
                            "n/a",
                        ),
                        "reference_aggregate_fuel_proxy_kgph": best_candidate.get("calm_water_metrics", {}).get(
                            "reference_aggregate_fuel_proxy_kgph",
                            "n/a",
                        ),
                        "power_improvement_pct": best_candidate.get("calm_water_metrics", {}).get(
                            "power_improvement_pct",
                            "n/a",
                        ),
                        "fuel_improvement_pct": best_candidate.get("calm_water_metrics", {}).get(
                            "fuel_improvement_pct",
                            "n/a",
                        ),
                        "reference_vs_candidate": "stable"
                        if best_candidate.get("acceptability", {}).get("is_acceptable", True)
                        else "review_required",
                    }
                )
                wave_response_summary = self._format_wave_response_summary(
                    {
                        "wave_height_m": best_candidate.get("wave_response_metrics", {}).get("wave_height_m", "n/a"),
                        "wave_period_s": best_candidate.get("wave_response_metrics", {}).get("wave_period_s", "n/a"),
                        "scenario_source": best_candidate.get("wave_response_metrics", {}).get("scenario_source", "n/a"),
                        "scenario_count": best_candidate.get("wave_response_metrics", {}).get("scenario_count", "n/a"),
                        "dominant_scenario_label": best_candidate.get(
                            "wave_response_metrics",
                            {},
                        ).get("dominant_scenario_label", "n/a"),
                        "added_resistance_proxy": best_candidate.get("wave_response_metrics", {}).get(
                            "added_resistance_proxy",
                            "n/a",
                        ),
                        "added_power_proxy_kw": best_candidate.get("wave_response_metrics", {}).get(
                            "added_power_proxy_kw",
                            "n/a",
                        ),
                        "wave_penalty": score_components.get("wave_penalty", "n/a"),
                        "condition_status": best_candidate.get("wave_response_metrics", {}).get(
                            "condition_status",
                            "n/a",
                        ),
                    }
                )
                multi_condition_summary = self._format_multi_condition_summary(
                    best_candidate.get("multi_condition_objective", {})
                )

        if metadata_path.exists():
            metadata_payload = self._json_store.read(metadata_path)
            command_payload = metadata_payload.get("create_case_command", {})
            runtime_budget = command_payload.get("runtime_budget_hours", "n/a")
            candidate_count = command_payload.get("candidate_count", "n/a")
            processed_count = len(candidate_rows)
            execution_summary = self._format_execution_summary(
                {
                    "runtime_budget_hours": runtime_budget,
                    "candidate_count": candidate_count,
                    "processed_candidates": processed_count,
                }
            )
            operational_profile_summary = self._format_operational_profile_summary(
                {
                    "profile_source": "user_defined" if command_payload.get("operational_profile_weights") else "derived_from_speed_knots",
                    "dominant_speed_knots": max(command_payload.get("speed_knots", []) or ["n/a"]),
                    "speed_knots": command_payload.get("speed_knots", []),
                    "operational_profile_weights": command_payload.get("operational_profile_weights")
                    or [],
                }
            )

        if optimization_path.exists():
            optimization_payload = self._json_store.read(optimization_path)
            optimization_summary = self._format_optimization_summary(optimization_payload)

        if artifacts_path.exists():
            artifacts_payload = self._json_store.read(artifacts_path)
            best_candidate_stl = artifacts_payload.get("best_candidate_stl")
            if best_candidate_stl:
                best_candidate_path = Path(best_candidate_stl)

        return {
            "geometry": geometry_summary,
            "evaluation": evaluation_summary,
            "execution": execution_summary,
            "operational_profile": operational_profile_summary,
            "weights": weights_summary,
            "thresholds": thresholds_summary,
            "hydrostatics": hydrostatics_summary,
            "calm_water": calm_water_summary,
            "wave_response": wave_response_summary,
            "baseline": baseline_summary,
            "multi_condition": multi_condition_summary,
            "high_fidelity_boundary": high_fidelity_boundary_summary,
            "acceptability": acceptability_summary,
            "optimization": optimization_summary,
            "candidates": candidates_summary,
            "rejected_candidates": rejected_candidates_summary,
            "optimization_trace": optimization_trace_summary,
            "candidate_rows": candidate_rows,
            "rejected_candidate_rows": rejected_candidate_rows,
            "optimization_trace_rows": optimization_trace_rows,
            "best_candidate_path": best_candidate_path,
        }

    def _build_results_from_case_summary(self, summary_metrics: dict) -> dict[str, str | list[str] | Path | None]:
        geometry_payload = summary_metrics.get("geometry", {})
        evaluation_payload = summary_metrics.get("evaluation", {})
        execution_payload = summary_metrics.get("execution", {})
        operational_profile_payload = summary_metrics.get("operational_profile", {})
        weights_payload = summary_metrics.get("objective_weights", {})
        thresholds_payload = summary_metrics.get("acceptability_thresholds", {})
        hydrostatics_payload = summary_metrics.get("hydrostatics", {})
        calm_water_payload = summary_metrics.get("calm_water", {})
        wave_response_payload = summary_metrics.get("wave_response", {})
        baseline_payload = summary_metrics.get("baseline", {})
        multi_condition_payload = summary_metrics.get("multi_condition_objective", {})
        high_fidelity_boundary_payload = summary_metrics.get("high_fidelity_boundary", {})
        if not baseline_payload and calm_water_payload:
            baseline_payload = {
                "reference_aggregate_power_proxy_kw": calm_water_payload.get("reference_aggregate_power_proxy_kw"),
                "reference_aggregate_fuel_proxy_kgph": calm_water_payload.get("reference_aggregate_fuel_proxy_kgph"),
                "power_improvement_pct": calm_water_payload.get("power_improvement_pct"),
                "fuel_improvement_pct": calm_water_payload.get("fuel_improvement_pct"),
                "reference_vs_candidate": "stable",
            }
        acceptability_payload = summary_metrics.get("acceptability", {})
        optimization_payload = summary_metrics.get("optimization", {})
        optimization_trace_payload = summary_metrics.get("optimization_trace", {})
        candidates_payload = summary_metrics.get("candidates", {})
        rejected_candidates_payload = summary_metrics.get("rejected_candidates", {})
        best_candidate_geometry_path = evaluation_payload.get("best_candidate_geometry_path")
        return {
            "geometry": self._format_geometry_summary(geometry_payload),
            "evaluation": self._format_evaluation_summary(evaluation_payload),
            "execution": self._format_execution_summary(execution_payload),
            "operational_profile": self._format_operational_profile_summary(operational_profile_payload),
            "weights": self._format_weights_summary(weights_payload),
            "thresholds": self._format_acceptability_thresholds_summary(thresholds_payload),
            "hydrostatics": self._format_hydrostatics_summary(hydrostatics_payload),
            "calm_water": self._format_calm_water_summary(calm_water_payload),
            "wave_response": self._format_wave_response_summary(wave_response_payload),
            "baseline": self._format_baseline_summary(baseline_payload),
            "multi_condition": self._format_multi_condition_summary(multi_condition_payload),
            "high_fidelity_boundary": self._format_high_fidelity_boundary_summary(high_fidelity_boundary_payload),
            "acceptability": self._format_acceptability_summary(acceptability_payload),
            "optimization": self._format_optimization_summary(optimization_payload),
            "candidates": candidates_payload.get("summary", "Candidates summary: not available"),
            "rejected_candidates": rejected_candidates_payload.get("summary", "Rejected candidates: not available"),
            "optimization_trace": optimization_trace_payload.get("summary", "Optimization trace: not available"),
            "candidate_rows": candidates_payload.get("rows", []),
            "rejected_candidate_rows": rejected_candidates_payload.get("rows", []),
            "optimization_trace_rows": optimization_trace_payload.get("rows", []),
            "best_candidate_path": Path(best_candidate_geometry_path) if best_candidate_geometry_path else None,
        }

    def _populate_candidates_table(self, candidate_rows: list[str]) -> None:
        if self._candidates_table_widget is None:
            return

        self._candidates_table_widget.setSortingEnabled(False)
        self._candidates_table_widget.setRowCount(len(candidate_rows))
        for row_index, row_text in enumerate(candidate_rows):
            columns = self._parse_candidate_row(row_text)
            for column_index, value in enumerate(columns):
                item = self._build_candidate_table_item(column_index, value)
                if column_index == 1:
                    item.setBackground(QBrush(self._level_color(value)))
                self._candidates_table_widget.setItem(row_index, column_index, item)
        self._candidates_table_widget.setSortingEnabled(True)
        if self._current_sort_column >= 0:
            self._candidates_table_widget.sortItems(self._current_sort_column, self._current_sort_order)

    def _apply_candidate_filter(self, filter_name: str) -> None:
        if self._candidates_table_widget is None or self._candidate_filter_summary_label is None:
            return

        if filter_name == "Rejected":
            filtered_rows = [row for row in self._candidate_rows_all if "| level=reject |" in row]
        elif filter_name == "Acceptable":
            filtered_rows = [row for row in self._candidate_rows_all if "| level=reject |" not in row]
        else:
            filtered_rows = list(self._candidate_rows_all)
        self._populate_candidates_table(filtered_rows)
        self._candidate_filter_summary_label.setText(
            f"Candidates shown: {len(filtered_rows)}/{len(self._candidate_rows_all)}"
        )

    def _remember_sort_state(self, column: int, order: Qt.SortOrder) -> None:
        self._current_sort_column = int(column)
        self._current_sort_order = order

    def _format_geometry_summary(self, payload: dict) -> str:
        summary = (
            "Geometry summary: "
            f"V={payload.get('vertices_count', 'n/a')} "
            f"F={payload.get('faces_count', 'n/a')} "
            f"watertight={'yes' if payload.get('watertight') else 'no'} "
            f"axis={payload.get('primary_axis', 'n/a')}"
        )
        if "slenderness_ratio" in payload:
            summary = f"{summary} slenderness={payload.get('slenderness_ratio', 'n/a')}"
        return summary

    def _format_evaluation_summary(self, payload: dict) -> str:
        return (
            "Evaluation summary: "
            f"{payload.get('best_candidate_id', 'n/a')} "
            f"fast={payload.get('fast_score', 'n/a')} "
            f"mid={payload.get('mid_score', 'n/a')} "
            f"resistance={payload.get('resistance_proxy', 'n/a')}"
        )

    def _format_execution_summary(self, payload: dict) -> str:
        return (
            "Execution summary: "
            f"runtime={payload.get('runtime_budget_hours', 'n/a')} h "
            f"candidates={payload.get('candidate_count', 'n/a')} "
            f"processed={payload.get('processed_candidates', 'n/a')}"
        )

    def _format_optimization_summary(self, payload: dict) -> str:
        return (
            "Optimization summary: "
            f"best={payload.get('best_candidate_id', 'n/a')} "
            f"ranked={payload.get('ranked_count', 'n/a')} "
            f"acceptable={payload.get('acceptable_count', 'n/a')} "
            f"warn={payload.get('warn_count', 'n/a')} "
            f"reject={payload.get('reject_count', 'n/a')} "
            f"spread={payload.get('mid_score_spread', 'n/a')}"
        )

    def _format_weights_summary(self, payload: dict) -> str:
        return (
            "Objective weights: "
            f"resistance={payload.get('resistance_weight', 'n/a')} "
            f"axial={payload.get('axial_gain_weight', 'n/a')} "
            f"draft={payload.get('draft_reduction_weight', 'n/a')} "
            f"beam={payload.get('beam_growth_weight', 'n/a')} "
            f"calm={payload.get('calm_water_condition_weight', 'n/a')} "
            f"wave={payload.get('wave_condition_weight', 'n/a')}"
        )

    def _format_operational_profile_summary(self, payload: dict) -> str:
        speeds = ",".join(str(value) for value in payload.get("speed_knots", [])) or "n/a"
        weights = ",".join(str(value) for value in payload.get("operational_profile_weights", [])) or "n/a"
        return (
            "Operational profile: "
            f"source={payload.get('profile_source', 'n/a')} "
            f"dominant={payload.get('dominant_speed_knots', 'n/a')} "
            f"speeds={speeds} "
            f"weights={weights}"
        )

    def _format_acceptability_thresholds_summary(self, payload: dict) -> str:
        return (
            "Acceptability thresholds: "
            f"warn_volume={payload.get('max_volume_delta_pct', 'n/a')} "
            f"warn_draft={payload.get('max_draft_delta_m', 'n/a')} "
            f"warn_speed_balance={payload.get('max_speed_balance_ratio', 'n/a')} "
            f"warn_wave={payload.get('max_wave_penalty', 'n/a')} "
            f"reject_volume={payload.get('reject_volume_delta_pct', 'n/a')} "
            f"reject_draft={payload.get('reject_draft_delta_m', 'n/a')} "
            f"reject_speed_balance={payload.get('reject_speed_balance_ratio', 'n/a')} "
            f"reject_wave={payload.get('reject_wave_penalty', 'n/a')}"
        )

    def _format_hydrostatics_summary(self, payload: dict) -> str:
        return (
            "Hydrostatics-lite: "
            f"status={payload.get('constraint_status', 'n/a')} "
            f"volume_delta={payload.get('volume_delta_pct', 'n/a')}% "
            f"draft_delta={payload.get('draft_delta_m', 'n/a')} "
            f"penalty={payload.get('hydrostatic_penalty', 'n/a')}"
        )

    def _format_calm_water_summary(self, payload: dict) -> str:
        return (
            "Calm-water surrogate: "
            f"speeds={payload.get('speed_count', 'n/a')} "
            f"dominant={payload.get('dominant_speed_knots', 'n/a')} "
            f"aggregate_power={payload.get('aggregate_power_proxy_kw', 'n/a')} "
            f"aggregate_fuel={payload.get('aggregate_fuel_proxy_kgph', 'n/a')} "
            f"aggregate_resistance={payload.get('aggregate_resistance_proxy', 'n/a')} "
            f"fuel_improvement={payload.get('fuel_improvement_pct', 'n/a')}% "
            f"penalty={payload.get('calm_water_penalty', 'n/a')}"
        )

    def _format_baseline_summary(self, payload: dict) -> str:
        return (
            "Baseline comparison: "
            f"reference_power={payload.get('reference_aggregate_power_proxy_kw', 'n/a')} "
            f"reference_fuel={payload.get('reference_aggregate_fuel_proxy_kgph', 'n/a')} "
            f"power_improvement={payload.get('power_improvement_pct', 'n/a')}% "
            f"fuel_improvement={payload.get('fuel_improvement_pct', 'n/a')}% "
            f"reference_vs_candidate={payload.get('reference_vs_candidate', 'n/a')}"
        )

    def _format_multi_condition_summary(self, payload: dict) -> str:
        return (
            "Multi-condition objective: "
            f"combined_penalty={payload.get('combined_penalty', 'n/a')} "
            f"dominant={payload.get('dominant_condition', 'n/a')} "
            f"score={payload.get('combined_objective_score', 'n/a')} "
            f"calm_weight={payload.get('calm_water_weight', 'n/a')} "
            f"wave_weight={payload.get('wave_response_weight', 'n/a')}"
        )

    def _format_high_fidelity_boundary_summary(self, payload: dict) -> str:
        if not payload:
            return "High-fidelity boundary: not available"
        return (
            "High-fidelity boundary: "
            f"adapter={payload.get('adapter', 'n/a')} "
            f"available={'yes' if payload.get('available') else 'no'} "
            f"used={'yes' if payload.get('used') else 'no'} "
            f"mode={payload.get('mode', 'n/a')}"
        )

    def _format_wave_response_summary(self, payload: dict) -> str:
        return (
            "Wave-response surrogate: "
            f"height={payload.get('wave_height_m', 'n/a')} "
            f"period={payload.get('wave_period_s', 'n/a')} "
            f"source={payload.get('scenario_source', 'n/a')} "
            f"scenarios={payload.get('scenario_count', 'n/a')} "
            f"dominant={payload.get('dominant_scenario_label', 'n/a')} "
            f"added_resistance={payload.get('added_resistance_proxy', 'n/a')} "
            f"added_power={payload.get('added_power_proxy_kw', 'n/a')} "
            f"penalty={payload.get('wave_penalty', 'n/a')} "
            f"status={payload.get('condition_status', 'n/a')}"
        )

    def _format_acceptability_summary(self, payload: dict) -> str:
        reasons = payload.get("reasons", [])
        reason_text = ",".join(str(value) for value in reasons) if reasons else "none"
        return (
            "Acceptability: "
            f"level={payload.get('level', 'n/a')} "
            f"acceptable={'yes' if payload.get('is_acceptable', False) else 'no'} "
            f"hydro={payload.get('hydrostatics_status', 'n/a')} "
            f"operational={payload.get('operational_profile_status', 'n/a')} "
            f"wave={payload.get('wave_response_status', 'n/a')} "
            f"reasons={reason_text}"
        )

    def _parse_candidate_row(self, row_text: str) -> list[str]:
        columns = {
            "candidate": "n/a",
            "level": "n/a",
            "fast": "n/a",
            "mid": "n/a",
            "resistance": "n/a",
            "hydro": "n/a",
            "calm": "n/a",
            "wave": "n/a",
            "reasons": "n/a",
        }
        segments = [segment.strip() for segment in row_text.split("|")]
        if segments:
            columns["candidate"] = segments[0]
        for segment in segments[1:]:
            if "=" not in segment:
                continue
            key, value = segment.split("=", 1)
            key = key.strip()
            if key in columns:
                columns[key] = value.strip()

        return [
            columns["candidate"],
            columns["level"],
            columns["fast"],
            columns["mid"],
            columns["resistance"],
            columns["hydro"],
            columns["calm"],
            columns["wave"],
            columns["reasons"],
        ]

    def _build_candidate_table_item(self, column_index: int, value: str) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        if column_index in {2, 3, 4, 5, 6, 7}:
            try:
                item.setData(Qt.EditRole, float(value))
            except (TypeError, ValueError):
                item.setData(Qt.EditRole, value)
        return item

    def _level_color(self, level: str) -> QColor:
        normalized = str(level).strip().lower()
        if normalized == "ok":
            return QColor("#d9f2d9")
        if normalized == "warn":
            return QColor("#fff1cc")
        if normalized == "reject":
            return QColor("#f4cccc")
        return QColor("#ffffff")
