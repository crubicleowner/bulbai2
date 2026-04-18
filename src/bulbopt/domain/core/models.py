from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class CaseStatus(str, Enum):
    DRAFT = 'draft'
    IMPORTED = 'imported'
    VALIDATED = 'validated'
    REPAIRING_GEOMETRY = 'repairing_geometry'
    GEOMETRY_READY = 'geometry_ready'
    BULB_REGION_PENDING_CONFIRMATION = 'bulb_region_pending_confirmation'
    READY_FOR_OPTIMIZATION = 'ready_for_optimization'
    RUNNING_FAST_SCREENING = 'running_fast_screening'
    RUNNING_MID_FIDELITY = 'running_mid_fidelity'
    RUNNING_HIGH_FIDELITY = 'running_high_fidelity'
    ASSEMBLING_RESULTS = 'assembling_results'
    COMPLETED = 'completed'
    COMPLETED_WITH_WARNINGS = 'completed_with_warnings'
    PAUSED = 'paused'
    FAILED = 'failed'


@dataclass(slots=True)
class CandidateVariant:
    candidate_id: str
    geometry_path: str
    status: str = 'generated'
    score: float | None = None
    error_code: str | None = None
    retry_count: int = 0
    can_retry: bool = True


@dataclass(slots=True)
class OptimizationCase:
    case_id: str
    case_name: str
    status: CaseStatus
    created_at: str
    updated_at: str
    is_recoverable: bool
    source_path: str | None = None
    candidates: list[CandidateVariant] = field(default_factory=list)

    @classmethod
    def new(cls, case_id: str, case_name: str) -> 'OptimizationCase':
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        return cls(
            case_id=case_id,
            case_name=case_name,
            status=CaseStatus.DRAFT,
            created_at=now,
            updated_at=now,
            is_recoverable=False,
        )
