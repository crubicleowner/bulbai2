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
