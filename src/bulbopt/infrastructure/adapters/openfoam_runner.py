from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from bulbopt.infrastructure.adapters.openfoam_adapter import (
    OpenFOAMAdapter,
    _configured_bin_dir,
    _shorten_path,
)


class OpenFOAMRunnerAdapter:
    """Optional runner boundary for worker-driven CFD execution (spec §4.8)."""

    DEFAULT_SOLVER_CHAIN: tuple[tuple[str, ...], ...] = (
        ("blockMesh",),
        ("snappyHexMesh", "-overwrite"),
    )

    def is_available(self) -> bool:
        return OpenFOAMAdapter().is_available()

    def run_case(
        self,
        openfoam_case_dir: Path,
        *,
        case_manifest: dict | None = None,
        execute: bool = False,
        timeout_seconds: int = 600,
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

        if execute:
            return self._execute_solver_chain(
                openfoam_case_dir=openfoam_case_dir,
                manifest=manifest,
                run_manifest_path=run_manifest_path,
                timeout_seconds=timeout_seconds,
            )

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

    def _execute_solver_chain(
        self,
        *,
        openfoam_case_dir: Path,
        manifest: dict,
        run_manifest_path: Path,
        timeout_seconds: int,
    ) -> dict[str, bool | str]:
        executed_steps: list[dict] = []
        overall_returncode = 0
        failing_step: str | None = None

        # Build subprocess env with the configured OpenFOAM bin directory
        # prepended to PATH. On Windows with non-ASCII install paths, switch
        # both cwd and bin_dir to their 8.3 short form so the MinGW dynamic
        # linker resolves the DLL dependencies.
        subprocess_env = os.environ.copy()
        bin_dir = _configured_bin_dir()
        if bin_dir:
            short_bin = _shorten_path(bin_dir)
            subprocess_env["PATH"] = short_bin + os.pathsep + subprocess_env.get("PATH", "")
        subprocess_cwd = _shorten_path(str(openfoam_case_dir))

        for command in self.DEFAULT_SOLVER_CHAIN:
            try:
                completed = subprocess.run(
                    command,
                    cwd=subprocess_cwd,
                    env=subprocess_env,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                step = {
                    "command": list(command),
                    "returncode": int(completed.returncode),
                    "stdout_tail": (completed.stdout or "")[-2000:],
                    "stderr_tail": (completed.stderr or "")[-2000:],
                }
                executed_steps.append(step)
                if completed.returncode != 0:
                    overall_returncode = completed.returncode
                    failing_step = command[0]
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
                executed_steps.append(
                    {
                        "command": list(command),
                        "returncode": -1,
                        "error": str(exc),
                    }
                )
                overall_returncode = -1
                failing_step = command[0]
                break

        status = "executed_ok" if overall_returncode == 0 and failing_step is None else "executed_failed"
        reason = (
            "solver_chain_completed"
            if status == "executed_ok"
            else f"solver_chain_failed_at_{failing_step or 'unknown'}"
        )
        result = {
            "runner_status": status,
            "runner_reason": reason,
            "runner_recoverable": True,
            "runner_case_directory": str(openfoam_case_dir),
            "status": status,
            "reason": reason,
            "is_recoverable": True,
            "best_candidate_id": manifest.get("best_candidate_id"),
            "executed_steps": executed_steps,
            "high_fidelity_used": status == "executed_ok",
        }
        run_manifest_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    def _read_case_manifest(self, openfoam_case_dir: Path) -> dict:
        manifest_path = openfoam_case_dir / "openfoam_case_manifest.json"
        return json.loads(manifest_path.read_text(encoding="utf-8"))
