from __future__ import annotations

import json
from pathlib import Path

from bulbopt.infrastructure.adapters.openfoam_adapter import OpenFOAMAdapter


class OpenFOAMRunnerAdapter:
    """Optional runner boundary for future worker-driven CFD execution."""

    def is_available(self) -> bool:
        return OpenFOAMAdapter().is_available()

    def run_case(
        self,
        openfoam_case_dir: Path,
        *,
        case_manifest: dict | None = None,
    ) -> dict[str, bool | str]:
        manifest = case_manifest or self._read_case_manifest(openfoam_case_dir)
        run_manifest_path = openfoam_case_dir / "openfoam_run_manifest.json"

        if not self.is_available():
            result = {
                "runner_status": "skipped",
                "runner_reason": "openfoam_unavailable",
                "runner_recoverable": True,
                "runner_case_directory": str(openfoam_case_dir),
                "status": "skipped",
                "reason": "openfoam_unavailable",
                "is_recoverable": True,
            }
            run_manifest_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result

        result = {
            "runner_status": "ready",
            "runner_reason": "available_for_execution",
            "runner_recoverable": True,
            "runner_case_directory": str(openfoam_case_dir),
            "recommended_commands": [
                "blockMesh",
                "snappyHexMesh -overwrite",
                "interFoam",
            ],
            "status": "ready",
            "reason": "available_for_execution",
            "is_recoverable": True,
            "best_candidate_id": manifest.get("best_candidate_id"),
        }
        run_manifest_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    def _read_case_manifest(self, openfoam_case_dir: Path) -> dict:
        manifest_path = openfoam_case_dir / "openfoam_case_manifest.json"
        return json.loads(manifest_path.read_text(encoding="utf-8"))
