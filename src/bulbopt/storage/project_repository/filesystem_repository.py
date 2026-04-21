from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
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

    def create_case(
        self,
        case: OptimizationCase,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        case_dir = self.case_dir(case.case_id)
        if case_dir.exists():
            raise FileExistsError(f"Case already exists: {case.case_id}")
        try:
            self._create_case_tree(case_dir)
            self.json_store.write(case_dir / "case.json", self._case_payload(case))
            self.json_store.write(case_dir / "metadata.json", self._metadata_payload(metadata))
            self.json_store.write(case_dir / "artifacts_index.json", {})
            self.json_store.write(case_dir / "candidate_index.json", [])
            self.json_store.write(case_dir / "evaluation_index.json", [])
        except Exception:
            shutil.rmtree(case_dir, ignore_errors=True)
            raise
        return case_dir

    def save_case(self, case: OptimizationCase) -> None:
        case_dir = self._require_existing_case(case.case_id)
        case.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.json_store.write(case_dir / "case.json", self._case_payload(case))

    def save_candidate_index(self, case_id: str, payload: list[dict[str, Any]]) -> None:
        case_dir = self._require_existing_case(case_id)
        self.json_store.write(case_dir / "candidate_index.json", payload)

    def list_cases(self) -> list[dict[str, Any]]:
        """Enumerate persisted cases so the UI can offer continuation (spec §10).

        Returns a list of summaries ordered by ``updated_at`` descending (most
        recently touched first). Non-case folders and case folders lacking a
        readable ``case.json`` are skipped so a single bad case never breaks
        the whole listing.
        """

        if not self.root_dir.exists():
            return []

        summaries: list[dict[str, Any]] = []
        for child in sorted(self.root_dir.iterdir()):
            if not child.is_dir():
                continue
            case_json = child / "case.json"
            if not case_json.exists():
                continue
            try:
                payload = self.json_store.read(case_json)
            except (OSError, ValueError):
                continue
            summaries.append(
                {
                    "case_id": payload.get("case_id", child.name),
                    "case_name": payload.get("case_name", ""),
                    "status": payload.get("status", "unknown"),
                    "is_recoverable": bool(payload.get("is_recoverable", False)),
                    "updated_at": payload.get("updated_at", ""),
                }
            )

        summaries.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return summaries

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

    def _metadata_payload(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        if metadata is None:
            return {}
        return {key: self._serialize_metadata_value(value) for key, value in metadata.items()}

    def _serialize_metadata_value(self, value: Any) -> Any:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return {key: self._serialize_metadata_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._serialize_metadata_value(item) for item in value]
        return value

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
