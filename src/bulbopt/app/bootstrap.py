from __future__ import annotations

from pathlib import Path

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.application.use_cases.run_vertical_slice import (
    resume_vertical_slice,
    run_vertical_slice,
)
from bulbopt.infrastructure.adapters.openfoam_adapter import detect_openfoam_available
from bulbopt.infrastructure.adapters.stub_geometry import StubGeometryAdapter
from bulbopt.infrastructure.config.settings import Settings
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def bootstrap_application(project_root: Path) -> dict:
    settings = Settings(
        project_root=project_root,
        openfoam_available=detect_openfoam_available(),
    )
    repository = FilesystemProjectRepository(root_dir=settings.project_root)

    def runner(**kwargs):
        command = CreateCaseCommand(**kwargs)
        return run_vertical_slice(project_root=settings.project_root, command=command)

    def resume(case_id: str):
        return resume_vertical_slice(project_root=settings.project_root, case_id=case_id)

    def list_cases() -> list[dict]:
        return repository.list_cases()

    def detect_bulb_region(source_path: str) -> dict:
        from pathlib import Path as _Path

        return StubGeometryAdapter().detect_bulb_region(_Path(source_path))

    return {
        "settings": settings,
        "run_vertical_slice": runner,
        "resume_vertical_slice": resume,
        "list_cases": list_cases,
        "detect_bulb_region": detect_bulb_region,
        "repository": repository,
    }
