from __future__ import annotations

from pathlib import Path
from typing import Any

from bulbopt.storage.filesystem.json_store import JsonStore


class FileCheckpointStore:
    def __init__(self, root_dir: Path, json_store: JsonStore | None = None) -> None:
        self.root_dir = root_dir
        self.json_store = json_store or JsonStore()

    def save(self, case_id: str, stage_name: str, payload: Any) -> Path:
        checkpoint_path = self.root_dir / f"{case_id}-{stage_name}.json"
        self.json_store.write(checkpoint_path, payload)
        return checkpoint_path
