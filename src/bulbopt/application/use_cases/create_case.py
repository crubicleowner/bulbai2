from __future__ import annotations

from uuid import uuid4

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.domain.core.models import CaseStatus, OptimizationCase
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def create_case(
    command: CreateCaseCommand,
    repository: FilesystemProjectRepository,
) -> OptimizationCase:
    case = OptimizationCase.new(case_id=f"case-{uuid4().hex[:8]}", case_name=command.case_name)
    case.source_path = command.source_path
    case.status = CaseStatus.IMPORTED
    repository.create_case(case)
    return case
