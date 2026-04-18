from __future__ import annotations

from pathlib import Path

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.application.use_cases.run_vertical_slice import run_vertical_slice
from bulbopt.infrastructure.config.settings import Settings


def bootstrap_application(project_root: Path) -> dict:
    settings = Settings(project_root=project_root)

    def runner(**kwargs):
        command = CreateCaseCommand(**kwargs)
        return run_vertical_slice(project_root=settings.project_root, command=command)

    return {
        "settings": settings,
        "run_vertical_slice": runner,
    }
