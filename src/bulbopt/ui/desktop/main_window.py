from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from bulbopt.app.bootstrap import bootstrap_application


class MainWindow(QMainWindow):
    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BulbOpt Desktop")
        self.services = bootstrap_application(project_root=project_root)
        self._build_central_widget()

    def _build_central_widget(self) -> None:
        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)

        app_label = QLabel("BulbOpt Desktop", central_widget)
        app_label.setObjectName("app_name_label")
        ready_label = QLabel("Ready for STL-first vertical slice", central_widget)
        ready_label.setObjectName("ready_state_label")

        layout.addWidget(app_label)
        layout.addWidget(ready_label)
        layout.addStretch(1)

        self.setCentralWidget(central_widget)
