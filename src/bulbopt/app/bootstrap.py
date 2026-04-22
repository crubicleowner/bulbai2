from __future__ import annotations

from pathlib import Path

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.application.use_cases.run_night_optimization import (
    NightOptimizationConfig,
    run_night_optimization,
)
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

    def night_runner(**kwargs):
        """Night optimization entry point.

        Accepts either a CreateCaseCommand payload (``case_name``,
        ``source_path``, ...) plus night-specific overrides
        (``budget_hours``, ``population``, ``generations``,
        ``high_fidelity_budget``, ``seed``).
        """
        night_keys = {
            "budget_hours",
            "population",
            "generations",
            "high_fidelity_budget",
            "seed",
        }
        night_kwargs = {key: kwargs.pop(key) for key in list(kwargs) if key in night_keys}
        config = NightOptimizationConfig(
            runtime_budget_hours=float(night_kwargs.get("budget_hours", 8.0)),
            population=int(night_kwargs.get("population", 50)),
            generations=int(night_kwargs.get("generations", 20)),
            high_fidelity_budget=int(night_kwargs.get("high_fidelity_budget", 10)),
            seed=night_kwargs.get("seed"),
        )
        command = CreateCaseCommand(**kwargs)
        return run_night_optimization(
            project_root=settings.project_root,
            command=command,
            config=config,
        )

    return {
        "settings": settings,
        "run_vertical_slice": runner,
        "resume_vertical_slice": resume,
        "run_night_optimization": night_runner,
        "list_cases": list_cases,
        "detect_bulb_region": detect_bulb_region,
        "repository": repository,
    }
