from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def default_case_payload() -> dict[str, object]:
    return {
        "case_name": "stl-demo",
        "source_path": "",
        "import_format": "stl",
        "optimization_mode": "generate_new_bulb",
        "vessel_length_m": 142.0,
        "vessel_beam_m": 19.1,
        "vessel_draft_m": 6.0,
        "displacement_t": 8420.0,
        "speed_knots": [18.0, 20.0],
        "runtime_budget_hours": 8,
    }


class CaseWizard(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        payload = default_case_payload()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Case Wizard"))
        layout.addWidget(QLabel(f"Import format: {payload['import_format']}"))
        layout.addWidget(QLabel(f"Optimization mode: {payload['optimization_mode']}"))
