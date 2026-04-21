from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CreateCaseCommand:
    case_name: str
    source_path: str
    vessel_length_m: float
    vessel_beam_m: float
    vessel_draft_m: float
    displacement_t: float
    speed_knots: list[float]
    operational_profile_weights: list[float] | None = None
    wave_height_m: float = 0.0
    wave_period_s: float = 0.0
    wave_scenario_heights_m: list[float] | None = None
    wave_scenario_periods_s: list[float] | None = None
    wave_scenario_weights: list[float] | None = None
    calm_water_condition_weight: float = 0.7
    wave_condition_weight: float = 0.3
    import_format: str = 'stl'
    optimization_mode: str = 'generate_new_bulb'
    runtime_budget_hours: int = 8
    candidate_count: int = 3
    resistance_weight: float = 1.0
    axial_gain_weight: float = 0.8
    draft_reduction_weight: float = 0.1
    beam_growth_weight: float = 0.05
    max_volume_delta_pct: float = 4.5
    max_draft_delta_m: float = 0.05
    max_speed_balance_ratio: float = 4.0
    max_wave_penalty: float = 1.5
    reject_volume_delta_pct: float = 9.0
    reject_draft_delta_m: float = 0.1
    reject_speed_balance_ratio: float = 8.0
    reject_wave_penalty: float = 3.0
    bulb_region_axis_min_override: float | None = None
    bulb_region_axis_max_override: float | None = None


@dataclass(slots=True)
class CaseSummary:
    case_id: str
    case_name: str
    status: str
    best_candidate_id: str | None = None
