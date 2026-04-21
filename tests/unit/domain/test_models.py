from datetime import datetime

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.domain.core.models import CandidateVariant, CaseStatus, OptimizationCase


def test_create_case_command_defaults_to_stl_first_mode() -> None:
    command = CreateCaseCommand(
        case_name='dtmb-5415-demo',
        source_path='fixtures/dtmb5415.stl',
        vessel_length_m=142.0,
        vessel_beam_m=19.1,
        vessel_draft_m=6.0,
        displacement_t=8420.0,
        speed_knots=[18.0, 20.0],
    )

    assert command.import_format == 'stl'
    assert command.optimization_mode == 'generate_new_bulb'
    assert command.resistance_weight == 1.0
    assert command.axial_gain_weight == 0.8
    assert command.draft_reduction_weight == 0.1
    assert command.beam_growth_weight == 0.05
    assert command.operational_profile_weights is None
    assert command.wave_height_m == 0.0
    assert command.wave_period_s == 0.0
    assert command.wave_scenario_heights_m is None
    assert command.wave_scenario_periods_s is None
    assert command.wave_scenario_weights is None
    assert command.calm_water_condition_weight == 0.7
    assert command.wave_condition_weight == 0.3
    assert command.max_volume_delta_pct == 4.5
    assert command.max_draft_delta_m == 0.05
    assert command.max_speed_balance_ratio == 4.0
    assert command.max_wave_penalty == 1.5
    assert command.reject_volume_delta_pct == 9.0
    assert command.reject_draft_delta_m == 0.1
    assert command.reject_speed_balance_ratio == 8.0
    assert command.reject_wave_penalty == 3.0


def test_optimization_case_starts_in_draft_status() -> None:
    case = OptimizationCase.new(case_id='case-001', case_name='demo')

    assert case.status is CaseStatus.DRAFT
    assert case.is_recoverable is False
    created_at = datetime.fromisoformat(case.created_at)
    updated_at = datetime.fromisoformat(case.updated_at)

    assert created_at.tzinfo is not None
    assert created_at.utcoffset() is not None
    assert updated_at.tzinfo is not None
    assert updated_at.utcoffset() is not None


def test_candidate_variant_tracks_retry_metadata() -> None:
    candidate = CandidateVariant(candidate_id='cand-1', geometry_path='working/candidates/cand-1.stl')

    assert candidate.status == 'generated'
    assert candidate.retry_count == 0
    assert candidate.can_retry is True
    assert candidate.error_code is None
