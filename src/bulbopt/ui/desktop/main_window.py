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
        self._weights_summary_label: QLabel | None = None
        self._hydrostatics_summary_label: QLabel | None = None
        self._optimization_summary_label: QLabel | None = None
        self._candidates_summary_label: QLabel | None = None
        self._candidates_list_widget: QListWidget | None = None
        self._open_case_button: QPushButton | None = None
        self._open_report_button: QPushButton | None = None
        self._open_best_candidate_button: QPushButton | None = None
        self._last_case_dir: Path | None = None
        self._last_report_path: Path | None = None
        self._last_best_candidate_path: Path | None = None
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
        self._weights_summary_label = QLabel(
            "Objective weights: not available",
            central_widget,
        )
        self._weights_summary_label.setObjectName("weights_summary_label")
        self._hydrostatics_summary_label = QLabel(
            "Hydrostatics-lite: not available",
            central_widget,
        )
        self._hydrostatics_summary_label.setObjectName("hydrostatics_summary_label")
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
        self._open_best_candidate_button = QPushButton("Open Best Candidate STL", central_widget)
        self._open_best_candidate_button.setObjectName("open_best_candidate_button")
        self._open_best_candidate_button.setEnabled(False)
        self._open_best_candidate_button.clicked.connect(self._open_best_candidate)

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
        layout.addWidget(self._weights_summary_label)
        layout.addWidget(self._hydrostatics_summary_label)
        layout.addWidget(self._optimization_summary_label)
        layout.addWidget(self._candidates_summary_label)
        layout.addWidget(self._candidates_list_widget)
        layout.addWidget(self._open_case_button)
        layout.addWidget(self._open_report_button)
        layout.addWidget(self._open_best_candidate_button)
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
            or self._weights_summary_label is None
            or self._hydrostatics_summary_label is None
            or self._optimization_summary_label is None
            or self._candidates_summary_label is None
            or self._candidates_list_widget is None
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
        self._weights_summary_label.setText("Objective weights: not available")
        self._hydrostatics_summary_label.setText("Hydrostatics-lite: not available")
        self._optimization_summary_label.setText("Optimization summary: not available")
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
        self._geometry_summary_label.setText(results_payload["geometry"])
        self._evaluation_summary_label.setText(results_payload["evaluation"])
        self._execution_summary_label.setText(results_payload["execution"])
        self._weights_summary_label.setText(results_payload["weights"])
        self._hydrostatics_summary_label.setText(results_payload["hydrostatics"])
        self._optimization_summary_label.setText(results_payload["optimization"])
        self._candidates_summary_label.setText(results_payload["candidates"])
        self._candidates_list_widget.addItems(results_payload["candidate_rows"])
        self._open_case_button.setEnabled(True)
        self._open_report_button.setEnabled(True)
        self._open_best_candidate_button.setEnabled(self._last_best_candidate_path is not None)

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
        weights_summary = "Objective weights: not available"
        hydrostatics_summary = "Hydrostatics-lite: not available"
        optimization_summary = "Optimization summary: not available"
        candidates_summary = "Candidates summary: not available"
        candidate_rows: list[str] = []
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
                weights_summary = summary_results["weights"]
                hydrostatics_summary = summary_results["hydrostatics"]
                optimization_summary = summary_results["optimization"]
                candidates_summary = summary_results["candidates"]
                candidate_rows = summary_results["candidate_rows"]
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
            "weights": weights_summary,
            "hydrostatics": hydrostatics_summary,
            "optimization": optimization_summary,
            "candidates": candidates_summary,
            "candidate_rows": candidate_rows,
            "best_candidate_path": best_candidate_path,
        }

    def _build_results_from_case_summary(self, summary_metrics: dict) -> dict[str, str | list[str] | Path | None]:
        geometry_payload = summary_metrics.get("geometry", {})
        evaluation_payload = summary_metrics.get("evaluation", {})
        execution_payload = summary_metrics.get("execution", {})
        weights_payload = summary_metrics.get("objective_weights", {})
        hydrostatics_payload = summary_metrics.get("hydrostatics", {})
        optimization_payload = summary_metrics.get("optimization", {})
        candidates_payload = summary_metrics.get("candidates", {})
        best_candidate_geometry_path = evaluation_payload.get("best_candidate_geometry_path")
        return {
            "geometry": self._format_geometry_summary(geometry_payload),
            "evaluation": self._format_evaluation_summary(evaluation_payload),
            "execution": self._format_execution_summary(execution_payload),
            "weights": self._format_weights_summary(weights_payload),
            "hydrostatics": self._format_hydrostatics_summary(hydrostatics_payload),
            "optimization": self._format_optimization_summary(optimization_payload),
            "candidates": candidates_payload.get("summary", "Candidates summary: not available"),
            "candidate_rows": candidates_payload.get("rows", []),
            "best_candidate_path": Path(best_candidate_geometry_path) if best_candidate_geometry_path else None,
        }

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
            f"spread={payload.get('mid_score_spread', 'n/a')}"
        )

    def _format_weights_summary(self, payload: dict) -> str:
        return (
            "Objective weights: "
            f"resistance={payload.get('resistance_weight', 'n/a')} "
            f"axial={payload.get('axial_gain_weight', 'n/a')} "
            f"draft={payload.get('draft_reduction_weight', 'n/a')} "
            f"beam={payload.get('beam_growth_weight', 'n/a')}"
        )

    def _format_hydrostatics_summary(self, payload: dict) -> str:
        return (
            "Hydrostatics-lite: "
            f"status={payload.get('constraint_status', 'n/a')} "
            f"volume_delta={payload.get('volume_delta_pct', 'n/a')}% "
            f"draft_delta={payload.get('draft_delta_m', 'n/a')} "
            f"penalty={payload.get('hydrostatic_penalty', 'n/a')}"
        )
