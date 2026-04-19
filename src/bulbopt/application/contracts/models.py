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
    import_format: str = 'stl'
    optimization_mode: str = 'generate_new_bulb'
    runtime_budget_hours: int = 8
    candidate_count: int = 3
    resistance_weight: float = 1.0
    axial_gain_weight: float = 0.8
    draft_reduction_weight: float = 0.1
    beam_growth_weight: float = 0.05


@dataclass(slots=True)
class CaseSummary:
    case_id: str
    case_name: str
    status: str
    best_candidate_id: str | None = None
