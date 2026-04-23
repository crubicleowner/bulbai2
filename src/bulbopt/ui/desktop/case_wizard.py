from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
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
        "operational_profile_weights": None,
        "wave_height_m": 0.0,
        "wave_period_s": 0.0,
        "wave_scenario_heights_m": None,
        "wave_scenario_periods_s": None,
        "wave_scenario_weights": None,
        "calm_water_condition_weight": 0.7,
        "wave_condition_weight": 0.3,
        "runtime_budget_hours": 8,
        "candidate_count": 3,
        "resistance_weight": 1.0,
        "axial_gain_weight": 0.8,
        "draft_reduction_weight": 0.1,
        "beam_growth_weight": 0.05,
        "max_volume_delta_pct": 4.5,
        "max_draft_delta_m": 0.05,
        "max_speed_balance_ratio": 4.0,
        "max_wave_penalty": 1.5,
        "reject_volume_delta_pct": 9.0,
        "reject_draft_delta_m": 0.1,
        "reject_speed_balance_ratio": 8.0,
        "reject_wave_penalty": 3.0,
        "bulb_region_axis_min_override": None,
        "bulb_region_axis_max_override": None,
    }


class CaseWizard(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        payload = default_case_payload()
        self._import_format = str(payload["import_format"])

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Case Wizard"))
        layout.addWidget(QLabel(f"Import format: {self._import_format}"))

        self._optimization_mode_combo = QComboBox(self)
        self._optimization_mode_combo.setObjectName("optimization_mode_combo")
        self._optimization_mode_combo.addItems(["generate_new_bulb", "local_optimize"])
        default_mode = str(payload["optimization_mode"])
        default_index = self._optimization_mode_combo.findText(default_mode)
        if default_index >= 0:
            self._optimization_mode_combo.setCurrentIndex(default_index)

        self._case_name_input = QLineEdit(str(payload["case_name"]), self)
        self._case_name_input.setObjectName("case_name_input")
        self._source_path_input = QLineEdit(str(payload["source_path"]), self)
        self._source_path_input.setObjectName("source_path_input")
        self._source_path_input.textChanged.connect(self._sync_source_label)
        self._vessel_length_input = self._make_float_input(float(payload["vessel_length_m"]), "vessel_length_input")
        self._vessel_beam_input = self._make_float_input(float(payload["vessel_beam_m"]), "vessel_beam_input")
        self._vessel_draft_input = self._make_float_input(float(payload["vessel_draft_m"]), "vessel_draft_input")
        self._displacement_input = self._make_float_input(float(payload["displacement_t"]), "displacement_input")
        self._speed_profile_input = QLineEdit(
            ", ".join(str(value) for value in payload["speed_knots"]),
            self,
        )
        self._speed_profile_input.setObjectName("speed_profile_input")
        self._operational_profile_input = QLineEdit("", self)
        self._operational_profile_input.setObjectName("operational_profile_input")
        self._wave_height_input = self._make_weight_input(
            float(payload["wave_height_m"]),
            "wave_height_input",
        )
        self._wave_period_input = self._make_weight_input(
            float(payload["wave_period_s"]),
            "wave_period_input",
        )
        self._wave_scenario_heights_input = QLineEdit("", self)
        self._wave_scenario_heights_input.setObjectName("wave_scenario_heights_input")
        self._wave_scenario_periods_input = QLineEdit("", self)
        self._wave_scenario_periods_input.setObjectName("wave_scenario_periods_input")
        self._wave_scenario_weights_input = QLineEdit("", self)
        self._wave_scenario_weights_input.setObjectName("wave_scenario_weights_input")
        self._calm_water_condition_weight_input = self._make_weight_input(
            float(payload["calm_water_condition_weight"]),
            "calm_water_condition_weight_input",
        )
        self._wave_condition_weight_input = self._make_weight_input(
            float(payload["wave_condition_weight"]),
            "wave_condition_weight_input",
        )
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
        self._max_volume_delta_pct_input = self._make_weight_input(
            float(payload["max_volume_delta_pct"]),
            "max_volume_delta_pct_input",
        )
        self._max_draft_delta_m_input = self._make_weight_input(
            float(payload["max_draft_delta_m"]),
            "max_draft_delta_m_input",
        )
        self._max_speed_balance_ratio_input = self._make_weight_input(
            float(payload["max_speed_balance_ratio"]),
            "max_speed_balance_ratio_input",
        )
        self._max_wave_penalty_input = self._make_weight_input(
            float(payload["max_wave_penalty"]),
            "max_wave_penalty_input",
        )
        self._reject_volume_delta_pct_input = self._make_weight_input(
            float(payload["reject_volume_delta_pct"]),
            "reject_volume_delta_pct_input",
        )
        self._reject_draft_delta_m_input = self._make_weight_input(
            float(payload["reject_draft_delta_m"]),
            "reject_draft_delta_m_input",
        )
        self._reject_speed_balance_ratio_input = self._make_weight_input(
            float(payload["reject_speed_balance_ratio"]),
            "reject_speed_balance_ratio_input",
        )
        self._reject_wave_penalty_input = self._make_weight_input(
            float(payload["reject_wave_penalty"]),
            "reject_wave_penalty_input",
        )
        self._bulb_region_axis_min_override_input = QLineEdit("", self)
        self._bulb_region_axis_min_override_input.setObjectName("bulb_region_axis_min_override_input")
        self._bulb_region_axis_min_override_input.setPlaceholderText(
            "optional: override auto-detected axis_min"
        )
        self._bulb_region_axis_max_override_input = QLineEdit("", self)
        self._bulb_region_axis_max_override_input.setObjectName("bulb_region_axis_max_override_input")
        self._bulb_region_axis_max_override_input.setPlaceholderText(
            "optional: override auto-detected axis_max"
        )

        form_layout = QFormLayout()
        form_layout.addRow("Optimization mode", self._optimization_mode_combo)
        form_layout.addRow("Case name", self._case_name_input)
        form_layout.addRow("Source STL", self._source_path_input)
        form_layout.addRow("Length (m)", self._vessel_length_input)
        form_layout.addRow("Beam (m)", self._vessel_beam_input)
        form_layout.addRow("Draft (m)", self._vessel_draft_input)
        form_layout.addRow("Displacement (t)", self._displacement_input)
        form_layout.addRow("Speed profile (kn)", self._speed_profile_input)
        form_layout.addRow("Operational profile", self._operational_profile_input)
        form_layout.addRow("Wave height (m)", self._wave_height_input)
        form_layout.addRow("Wave period (s)", self._wave_period_input)
        form_layout.addRow("Wave scenario heights (m)", self._wave_scenario_heights_input)
        form_layout.addRow("Wave scenario periods (s)", self._wave_scenario_periods_input)
        form_layout.addRow("Wave scenario weights", self._wave_scenario_weights_input)
        form_layout.addRow("Calm-water weight", self._calm_water_condition_weight_input)
        form_layout.addRow("Wave weight", self._wave_condition_weight_input)
        form_layout.addRow("Runtime (h)", self._runtime_budget_input)
        form_layout.addRow("Candidates", self._candidate_count_input)
        form_layout.addRow("Resistance weight", self._resistance_weight_input)
        form_layout.addRow("Axial gain weight", self._axial_gain_weight_input)
        form_layout.addRow("Draft reduction weight", self._draft_reduction_weight_input)
        form_layout.addRow("Beam growth weight", self._beam_growth_weight_input)
        form_layout.addRow("Max volume delta (%)", self._max_volume_delta_pct_input)
        form_layout.addRow("Max draft delta (m)", self._max_draft_delta_m_input)
        form_layout.addRow("Max speed balance", self._max_speed_balance_ratio_input)
        form_layout.addRow("Max wave penalty", self._max_wave_penalty_input)
        form_layout.addRow("Reject volume delta (%)", self._reject_volume_delta_pct_input)
        form_layout.addRow("Reject draft delta (m)", self._reject_draft_delta_m_input)
        form_layout.addRow("Reject speed balance", self._reject_speed_balance_ratio_input)
        form_layout.addRow("Reject wave penalty", self._reject_wave_penalty_input)
        form_layout.addRow("Bulb axis_min override", self._bulb_region_axis_min_override_input)
        form_layout.addRow("Bulb axis_max override", self._bulb_region_axis_max_override_input)
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
            "optimization_mode": self._optimization_mode_combo.currentText(),
            "vessel_length_m": self._vessel_length_input.value(),
            "vessel_beam_m": self._vessel_beam_input.value(),
            "vessel_draft_m": self._vessel_draft_input.value(),
            "displacement_t": self._displacement_input.value(),
            "speed_knots": self._parse_float_list(
                self._speed_profile_input.text(),
                default=[18.0, 20.0],
            ),
            "operational_profile_weights": self._parse_optional_float_list(
                self._operational_profile_input.text(),
            ),
            "wave_height_m": self._wave_height_input.value(),
            "wave_period_s": self._wave_period_input.value(),
            "wave_scenario_heights_m": self._parse_optional_float_list(
                self._wave_scenario_heights_input.text(),
            ),
            "wave_scenario_periods_s": self._parse_optional_float_list(
                self._wave_scenario_periods_input.text(),
            ),
            "wave_scenario_weights": self._parse_optional_float_list(
                self._wave_scenario_weights_input.text(),
            ),
            "calm_water_condition_weight": self._calm_water_condition_weight_input.value(),
            "wave_condition_weight": self._wave_condition_weight_input.value(),
            "runtime_budget_hours": self._runtime_budget_input.value(),
            "candidate_count": self._candidate_count_input.value(),
            "resistance_weight": self._resistance_weight_input.value(),
            "axial_gain_weight": self._axial_gain_weight_input.value(),
            "draft_reduction_weight": self._draft_reduction_weight_input.value(),
            "beam_growth_weight": self._beam_growth_weight_input.value(),
            "max_volume_delta_pct": self._max_volume_delta_pct_input.value(),
            "max_draft_delta_m": self._max_draft_delta_m_input.value(),
            "max_speed_balance_ratio": self._max_speed_balance_ratio_input.value(),
            "max_wave_penalty": self._max_wave_penalty_input.value(),
            "reject_volume_delta_pct": self._reject_volume_delta_pct_input.value(),
            "reject_draft_delta_m": self._reject_draft_delta_m_input.value(),
            "reject_speed_balance_ratio": self._reject_speed_balance_ratio_input.value(),
            "reject_wave_penalty": self._reject_wave_penalty_input.value(),
            "bulb_region_axis_min_override": self._parse_optional_float(
                self._bulb_region_axis_min_override_input.text()
            ),
            "bulb_region_axis_max_override": self._parse_optional_float(
                self._bulb_region_axis_max_override_input.text()
            ),
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

    def _parse_float_list(self, raw_value: str, default: list[float]) -> list[float]:
        try:
            values = [float(item.strip()) for item in raw_value.split(",") if item.strip()]
        except ValueError:
            return default
        return values or default

    def _parse_optional_float_list(self, raw_value: str) -> list[float] | None:
        if not raw_value.strip():
            return None
        try:
            values = [float(item.strip()) for item in raw_value.split(",") if item.strip()]
        except ValueError:
            return None
        return values or None

    def _parse_optional_float(self, raw_value: str) -> float | None:
        stripped = raw_value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
