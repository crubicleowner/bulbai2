from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bulbopt.storage.filesystem.json_store import JsonStore


_VALID_NAME_PATTERN = re.compile(r"^[A-Za-z0-9]+(?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


class FileCheckpointStore:
    def __init__(self, root_dir: Path, json_store: JsonStore | None = None) -> None:
        self.root_dir = root_dir
        self.json_store = json_store or JsonStore()

    def save(self, case_id: str, stage_name: str, payload: Any) -> Path:
        self._validate_component(case_id, "case_id")
        self._validate_component(stage_name, "stage_name")
        checkpoint_path = self.root_dir / f"{case_id}-{stage_name}.json"
        self.json_store.write(checkpoint_path, payload)
        return checkpoint_path

    def _validate_component(self, value: str, field_name: str) -> None:
        component_path = Path(value)
        if component_path.is_absolute() or len(component_path.parts) != 1 or component_path.parts[0] in {".", ".."}:
            raise ValueError(f"Invalid {field_name}: {value}")

        if not _VALID_NAME_PATTERN.fullmatch(value):
            raise ValueError(f"Invalid {field_name}: {value}")
