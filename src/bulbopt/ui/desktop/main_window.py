from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from bulbopt.app.bootstrap import bootstrap_application
from bulbopt.ui.desktop.case_wizard import CaseWizard


class MainWindow(QMainWindow):
    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BulbOpt Desktop")
        self.services = bootstrap_application(project_root=project_root)
        self._case_wizard: CaseWizard | None = None
        self._run_status_label: QLabel | None = None
        self._artifacts_label: QLabel | None = None
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
        self._artifacts_label = QLabel("No artifacts yet", central_widget)
        self._artifacts_label.setObjectName("artifacts_label")

        layout.addWidget(app_label)
        layout.addWidget(ready_label)
        layout.addWidget(self._case_wizard)
        layout.addWidget(run_button)
        layout.addWidget(self._run_status_label)
        layout.addWidget(self._artifacts_label)
        layout.addStretch(1)

        self.setCentralWidget(central_widget)

    def _run_vertical_slice(self) -> None:
        if (
            self._case_wizard is None
            or self._run_status_label is None
            or self._artifacts_label is None
        ):
            return

        payload = self._case_wizard.payload()
        self._run_status_label.setText("Running vertical slice...")

        try:
            summary = self.services["run_vertical_slice"](**payload)
        except Exception as error:
            self._run_status_label.setText(f"Failed: {error}")
            self._artifacts_label.setText("Artifacts unavailable because execution failed")
            return

        project_root = self.services["settings"].project_root
        case_dir = project_root / summary.case_id
        report_path = case_dir / "outputs" / "reports" / "report.html"
        self._run_status_label.setText(
            "Completed: "
            f"{summary.case_id} | best candidate {summary.best_candidate_id or 'n/a'}"
        )
        self._artifacts_label.setText(
            f"Case: {case_dir} | Report: {report_path}"
        )
