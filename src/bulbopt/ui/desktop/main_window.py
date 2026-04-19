from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
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
        self._open_case_button: QPushButton | None = None
        self._open_report_button: QPushButton | None = None
        self._last_case_dir: Path | None = None
        self._last_report_path: Path | None = None
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
        layout.addWidget(self._open_case_button)
        layout.addWidget(self._open_report_button)
        layout.addStretch(1)

        self.setCentralWidget(central_widget)

    def _run_vertical_slice(self) -> None:
        if (
            self._case_wizard is None
            or self._run_status_label is None
            or self._artifacts_label is None
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
