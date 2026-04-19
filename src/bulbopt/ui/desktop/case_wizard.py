from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def discover_demo_source_path(start_path: Path | None = None) -> str:
    search_root = start_path or Path(__file__).resolve()

    for candidate_root in (search_root, *search_root.parents):
        demo_path = candidate_root / "docs" / "base_hull.stl"
        if demo_path.exists():
            return str(demo_path)

    return ""


def default_case_payload() -> dict[str, object]:
    return {
        "case_name": "stl-demo",
        "source_path": discover_demo_source_path(),
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

        self._payload = default_case_payload()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Case Wizard"))
        layout.addWidget(QLabel(f"Import format: {self._payload['import_format']}"))
        layout.addWidget(QLabel(f"Optimization mode: {self._payload['optimization_mode']}"))

        source_path = str(self._payload["source_path"]) or "Not found"
        source_label = QLabel(f"Source STL: {source_path}")
        source_label.setObjectName("source_path_label")
        layout.addWidget(source_label)

    def payload(self) -> dict[str, object]:
        return dict(self._payload)
