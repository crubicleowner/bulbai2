from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


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
        "candidate_count": 3,
        "resistance_weight": 1.0,
        "axial_gain_weight": 0.8,
        "draft_reduction_weight": 0.1,
        "beam_growth_weight": 0.05,
    }


class CaseWizard(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        payload = default_case_payload()
        self._import_format = str(payload["import_format"])
        self._optimization_mode = str(payload["optimization_mode"])

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Case Wizard"))
        layout.addWidget(QLabel(f"Import format: {self._import_format}"))
        layout.addWidget(QLabel(f"Optimization mode: {self._optimization_mode}"))

        self._case_name_input = QLineEdit(str(payload["case_name"]), self)
        self._case_name_input.setObjectName("case_name_input")
        self._source_path_input = QLineEdit(str(payload["source_path"]), self)
        self._source_path_input.setObjectName("source_path_input")
        self._source_path_input.textChanged.connect(self._sync_source_label)
        self._vessel_length_input = self._make_float_input(float(payload["vessel_length_m"]), "vessel_length_input")
        self._vessel_beam_input = self._make_float_input(float(payload["vessel_beam_m"]), "vessel_beam_input")
        self._vessel_draft_input = self._make_float_input(float(payload["vessel_draft_m"]), "vessel_draft_input")
        self._displacement_input = self._make_float_input(float(payload["displacement_t"]), "displacement_input")
        self._runtime_budget_input = QSpinBox(self)
        self._runtime_budget_input.setObjectName("runtime_budget_input")
        self._runtime_budget_input.setRange(1, 168)
        self._runtime_budget_input.setValue(int(payload["runtime_budget_hours"]))
        self._candidate_count_input = QSpinBox(self)
        self._candidate_count_input.setObjectName("candidate_count_input")
        self._candidate_count_input.setRange(1, 20)
        self._candidate_count_input.setValue(int(payload["candidate_count"]))
        self._resistance_weight_input = self._make_weight_input(
            float(payload["resistance_weight"]),
            "resistance_weight_input",
        )
        self._axial_gain_weight_input = self._make_weight_input(
            float(payload["axial_gain_weight"]),
            "axial_gain_weight_input",
        )
        self._draft_reduction_weight_input = self._make_weight_input(
            float(payload["draft_reduction_weight"]),
            "draft_reduction_weight_input",
        )
        self._beam_growth_weight_input = self._make_weight_input(
            float(payload["beam_growth_weight"]),
            "beam_growth_weight_input",
        )

        form_layout = QFormLayout()
        form_layout.addRow("Case name", self._case_name_input)
        form_layout.addRow("Source STL", self._source_path_input)
        form_layout.addRow("Length (m)", self._vessel_length_input)
        form_layout.addRow("Beam (m)", self._vessel_beam_input)
        form_layout.addRow("Draft (m)", self._vessel_draft_input)
        form_layout.addRow("Displacement (t)", self._displacement_input)
        form_layout.addRow("Runtime (h)", self._runtime_budget_input)
        form_layout.addRow("Candidates", self._candidate_count_input)
        form_layout.addRow("Resistance weight", self._resistance_weight_input)
        form_layout.addRow("Axial gain weight", self._axial_gain_weight_input)
        form_layout.addRow("Draft reduction weight", self._draft_reduction_weight_input)
        form_layout.addRow("Beam growth weight", self._beam_growth_weight_input)
        layout.addLayout(form_layout)

        source_path = self._source_path_input.text() or "Not found"
        source_label = QLabel(f"Source STL: {source_path}")
        source_label.setObjectName("source_path_label")
        self._source_label = source_label
        layout.addWidget(source_label)

    def payload(self) -> dict[str, object]:
        return {
            "case_name": self._case_name_input.text().strip() or "stl-demo",
            "source_path": self._source_path_input.text().strip(),
            "import_format": self._import_format,
            "optimization_mode": self._optimization_mode,
            "vessel_length_m": self._vessel_length_input.value(),
            "vessel_beam_m": self._vessel_beam_input.value(),
            "vessel_draft_m": self._vessel_draft_input.value(),
            "displacement_t": self._displacement_input.value(),
            "speed_knots": [18.0, 20.0],
            "runtime_budget_hours": self._runtime_budget_input.value(),
            "candidate_count": self._candidate_count_input.value(),
            "resistance_weight": self._resistance_weight_input.value(),
            "axial_gain_weight": self._axial_gain_weight_input.value(),
            "draft_reduction_weight": self._draft_reduction_weight_input.value(),
            "beam_growth_weight": self._beam_growth_weight_input.value(),
        }

    def _sync_source_label(self, value: str) -> None:
        self._source_label.setText(f"Source STL: {value or 'Not found'}")

    def _make_float_input(self, value: float, object_name: str) -> QDoubleSpinBox:
        widget = QDoubleSpinBox(self)
        widget.setObjectName(object_name)
        widget.setRange(0.1, 100000.0)
        widget.setDecimals(2)
        widget.setValue(value)
        return widget

    def _make_weight_input(self, value: float, object_name: str) -> QDoubleSpinBox:
        widget = QDoubleSpinBox(self)
        widget.setObjectName(object_name)
        widget.setRange(0.0, 10.0)
        widget.setDecimals(2)
        widget.setSingleStep(0.05)
        widget.setValue(value)
        return widget
