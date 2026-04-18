from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    project_root: Path
    openfoam_available: bool = False
    default_candidate_count: int = 3
