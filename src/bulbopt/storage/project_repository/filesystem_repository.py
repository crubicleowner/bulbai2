from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from bulbopt.domain.core.models import OptimizationCase
from bulbopt.storage.filesystem.json_store import JsonStore


class FilesystemProjectRepository:
    def __init__(self, root_dir: Path, json_store: JsonStore | None = None) -> None:
        self.root_dir = root_dir
        self.json_store = json_store or JsonStore()

    def case_dir(self, case_id: str) -> Path:
        self._validate_case_id(case_id)
        return self.root_dir / case_id

    def create_case(self, case: OptimizationCase) -> Path:
        case_dir = self.case_dir(case.case_id)
        if case_dir.exists():
            raise FileExistsError(f"Case already exists: {case.case_id}")
        self._create_case_tree(case_dir)
        self.json_store.write(case_dir / "case.json", self._case_payload(case))
        self.json_store.write(case_dir / "metadata.json", {})
        self.json_store.write(case_dir / "artifacts_index.json", {})
        self.json_store.write(case_dir / "candidate_index.json", [])
        self.json_store.write(case_dir / "evaluation_index.json", [])
        return case_dir

    def save_candidate_index(self, case_id: str, payload: list[dict[str, Any]]) -> None:
        case_dir = self._require_existing_case(case_id)
        self.json_store.write(case_dir / "candidate_index.json", payload)

    def _create_case_tree(self, case_dir: Path) -> None:
        for relative_path in [
            Path("input"),
            Path("working/repaired"),
            Path("working/masks"),
            Path("working/candidates"),
            Path("working/evaluation"),
            Path("working/checkpoints"),
            Path("outputs/geometry"),
            Path("outputs/reports"),
            Path("outputs/plots"),
            Path("outputs/tables"),
            Path("logs"),
        ]:
            (case_dir / relative_path).mkdir(parents=True, exist_ok=True)

    def _case_payload(self, case: OptimizationCase) -> dict[str, Any]:
        payload = asdict(case)
        payload["status"] = case.status.value
        return payload

    def _require_existing_case(self, case_id: str) -> Path:
        case_dir = self.case_dir(case_id)
        if not case_dir.exists():
            raise FileNotFoundError(f"Case directory does not exist: {case_id}")

        case_json = case_dir / "case.json"
        if not case_json.exists():
            raise FileNotFoundError(f"Missing case metadata: {case_json}")

        return case_dir

    def _validate_case_id(self, case_id: str) -> None:
        case_path = Path(case_id)
        if case_path.is_absolute():
            raise ValueError(f"Invalid case_id: {case_id}")

        parts = case_path.parts
        if len(parts) != 1 or parts[0] in {".", ".."}:
            raise ValueError(f"Invalid case_id: {case_id}")
