from __future__ import annotations

import json
from pathlib import Path

from bulbopt.execution.checkpoints.file_checkpoint_store import FileCheckpointStore
from bulbopt.execution.worker.local_worker import LocalWorker
from bulbopt.infrastructure.adapters.openfoam_adapter import OpenFOAMAdapter
from bulbopt.infrastructure.adapters.openfoam_runner import OpenFOAMRunnerAdapter


def test_openfoam_runner_returns_recoverable_skip_when_solver_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case_dir = tmp_path / "case"
    geometry_path = case_dir / "candidate.stl"
    geometry_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    builder = OpenFOAMAdapter()
    monkeypatch.setattr(builder, "is_available", lambda: False)
    manifest = builder.build_case(
        case_dir,
        best_candidate_id="candidate-7",
        best_candidate_geometry_path=geometry_path,
    )

    runner = OpenFOAMRunnerAdapter()
    monkeypatch.setattr(runner, "is_available", lambda: False)
    result = runner.run_case(case_dir / "working" / "openfoam_case", case_manifest=manifest)

    assert result["status"] == "skipped"
    assert result["reason"] == "openfoam_unavailable"
    assert result["is_recoverable"] is True
    assert (case_dir / "working" / "openfoam_case" / "openfoam_run_manifest.json").exists()


def test_openfoam_runner_can_be_executed_through_local_worker(tmp_path: Path, monkeypatch) -> None:
    case_dir = tmp_path / "case"
    geometry_path = case_dir / "candidate.stl"
    geometry_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    builder = OpenFOAMAdapter()
    monkeypatch.setattr(builder, "is_available", lambda: False)
    manifest = builder.build_case(
        case_dir,
        best_candidate_id="candidate-9",
        best_candidate_geometry_path=geometry_path,
    )

    runner = OpenFOAMRunnerAdapter()
    monkeypatch.setattr(runner, "is_available", lambda: False)
    worker = LocalWorker(checkpoint_store=FileCheckpointStore(root_dir=tmp_path / "checkpoints"))

    result = worker.run(
        "case-foam",
        "openfoam-runner",
        lambda: runner.run_case(case_dir / "working" / "openfoam_case", case_manifest=manifest),
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "openfoam_unavailable"
    checkpoint_payload = json.loads(
        (tmp_path / "checkpoints" / "case-foam-openfoam-runner.json").read_text(encoding="utf-8")
    )
    assert checkpoint_payload["status"] == "completed"
    assert checkpoint_payload["result"]["status"] == "skipped"
