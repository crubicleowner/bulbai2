from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QListWidget, QMainWindow, QPushButton, QVBoxLayout, QWidget

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
        self._candidates_summary_label: QLabel | None = None
        self._candidates_list_widget: QListWidget | None = None
        self._open_case_button: QPushButton | None = None
        self._open_report_button: QPushButton | None = None
        self._last_case_dir: Path | None = None
        self._last_report_path: Path | None = None
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
        self._candidates_summary_label = QLabel(
            "Candidates summary: not available",
            central_widget,
        )
        self._candidates_summary_label.setObjectName("candidates_summary_label")
        self._candidates_list_widget = QListWidget(central_widget)
        self._candidates_list_widget.setObjectName("candidates_list_widget")
        self._open_case_button = QPushButton("Open Case Folder", central_widget)
        self._open_case_button.setObjectName("open_case_button")
        self._open_case_button.setEnabled(False)
        self._open_case_button.clicked.connect(self._open_case_dir)
        self._open_report_button = QPushButton("Open Report", central_widget)
        self._open_report_button.setObjectName("open_report_button")
        self._open_report_button.setEnabled(False)
        self._open_report_button.clicked.connect(self._open_report)

        layout.addWidget(app_label)
        layout.addWidget(ready_label)
        layout.addWidget(self._case_wizard)
        layout.addWidget(run_button)
        layout.addWidget(self._run_status_label)
        layout.addWidget(results_label)
        layout.addWidget(self._artifacts_label)
        layout.addWidget(self._geometry_summary_label)
        layout.addWidget(self._evaluation_summary_label)
        layout.addWidget(self._execution_summary_label)
        layout.addWidget(self._candidates_summary_label)
        layout.addWidget(self._candidates_list_widget)
        layout.addWidget(self._open_case_button)
        layout.addWidget(self._open_report_button)
        layout.addStretch(1)

        self.setCentralWidget(central_widget)

    def _run_vertical_slice(self) -> None:
        if (
            self._case_wizard is None
            or self._run_status_label is None
            or self._artifacts_label is None
            or self._geometry_summary_label is None
            or self._evaluation_summary_label is None
            or self._execution_summary_label is None
            or self._candidates_summary_label is None
            or self._candidates_list_widget is None
            or self._open_case_button is None
            or self._open_report_button is None
        ):
            return

        payload = self._case_wizard.payload()
        self._run_status_label.setText("Running vertical slice...")
        self._last_case_dir = None
        self._last_report_path = None
        self._open_case_button.setEnabled(False)
        self._open_report_button.setEnabled(False)
        self._geometry_summary_label.setText("Geometry summary: not available")
        self._evaluation_summary_label.setText("Evaluation summary: not available")
        self._execution_summary_label.setText("Execution summary: not available")
        self._candidates_summary_label.setText("Candidates summary: not available")
        self._candidates_list_widget.clear()

        try:
            summary = self.services["run_vertical_slice"](**payload)
        except Exception as error:
            self._run_status_label.setText(f"Failed: {error}")
            self._artifacts_label.setText("Artifacts unavailable because execution failed")
            return

        project_root = self.services["settings"].project_root
        self._last_case_dir = project_root / summary.case_id
        self._last_report_path = self._last_case_dir / "outputs" / "reports" / "report.html"
        self._run_status_label.setText(
            "Completed: "
            f"{summary.case_id} | best candidate {summary.best_candidate_id or 'n/a'}"
        )
        self._artifacts_label.setText(
            f"Case: {self._last_case_dir} | Report: {self._last_report_path}"
        )
        results_payload = self._load_case_results(self._last_case_dir, summary.best_candidate_id)
        self._geometry_summary_label.setText(results_payload["geometry"])
        self._evaluation_summary_label.setText(results_payload["evaluation"])
        self._execution_summary_label.setText(results_payload["execution"])
        self._candidates_summary_label.setText(results_payload["candidates"])
        self._candidates_list_widget.addItems(results_payload["candidate_rows"])
        self._open_case_button.setEnabled(True)
        self._open_report_button.setEnabled(True)

    def _open_case_dir(self) -> None:
        if self._last_case_dir is not None:
            self._open_path(self._last_case_dir)

    def _open_report(self) -> None:
        if self._last_report_path is not None:
            self._open_path(self._last_report_path)

    def _open_path(self, path: Path) -> bool:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _load_case_results(self, case_dir: Path, best_candidate_id: str | None) -> dict[str, str]:
        geometry_summary = "Geometry summary: not available"
        evaluation_summary = "Evaluation summary: not available"
        execution_summary = "Execution summary: not available"
        candidates_summary = "Candidates summary: not available"
        candidate_rows: list[str] = []

        geometry_path = case_dir / "working" / "repaired" / "geometry_analysis.json"
        evaluation_path = case_dir / "evaluation_index.json"
        metadata_path = case_dir / "metadata.json"

        if geometry_path.exists():
            geometry_payload = self._json_store.read(geometry_path)
            quality_report = geometry_payload.get("quality_report", {})
            geometry_summary = (
                "Geometry summary: "
                f"V={quality_report.get('vertices_count', 'n/a')} "
                f"F={quality_report.get('faces_count', 'n/a')} "
                f"watertight={'yes' if quality_report.get('watertight') else 'no'} "
                f"axis={quality_report.get('primary_axis', 'n/a')}"
            )

        if evaluation_path.exists():
            evaluation_payload = self._json_store.read(evaluation_path)
            ranked_candidates = []
            for item in evaluation_payload:
                candidate_row = (
                    f"{item.get('candidate_id', 'n/a')} | "
                    f"fast={item.get('fast_score', 'n/a')} | "
                    f"mid={item.get('mid_score', 'n/a')}"
                )
                candidate_rows.append(candidate_row)
                ranked_candidates.append(f"{item.get('candidate_id', 'n/a')} mid={item.get('mid_score', 'n/a')}")
            if ranked_candidates:
                candidates_summary = "Candidates: " + " | ".join(ranked_candidates)

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
                geometry_summary = (
                    f"{geometry_summary} "
                    f"slenderness={geometry_metrics.get('slenderness_ratio', 'n/a')}"
                )
                evaluation_summary = (
                    "Evaluation summary: "
                    f"{best_candidate.get('candidate_id', 'n/a')} "
                    f"fast={best_candidate.get('fast_score', 'n/a')} "
                    f"mid={best_candidate.get('mid_score', 'n/a')} "
                    f"resistance={score_components.get('resistance_proxy', 'n/a')}"
                )

        if metadata_path.exists():
            metadata_payload = self._json_store.read(metadata_path)
            command_payload = metadata_payload.get("create_case_command", {})
            runtime_budget = command_payload.get("runtime_budget_hours", "n/a")
            candidate_count = command_payload.get("candidate_count", "n/a")
            processed_count = len(candidate_rows)
            execution_summary = (
                "Execution summary: "
                f"runtime={runtime_budget} h "
                f"candidates={candidate_count} "
                f"processed={processed_count}"
            )

        return {
            "geometry": geometry_summary,
            "evaluation": evaluation_summary,
            "execution": execution_summary,
            "candidates": candidates_summary,
            "candidate_rows": candidate_rows,
        }
