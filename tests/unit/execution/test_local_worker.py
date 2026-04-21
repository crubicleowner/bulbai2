from __future__ import annotations

import json
from pathlib import Path

from bulbopt.execution.checkpoints.file_checkpoint_store import FileCheckpointStore
from bulbopt.execution.worker.local_worker import LocalWorker


def test_local_worker_success_returns_job_result_and_writes_checkpoint(tmp_path: Path) -> None:
    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    result = worker.run("case-001", "stage-1", lambda: {"status": "ok"})

    assert result == {"status": "ok"}
    checkpoint_path = tmp_path / "case-001-stage-1.json"
    assert checkpoint_path.exists()
    checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_payload["status"] == "completed"
    assert checkpoint_payload["result"] == {"status": "ok"}
    assert checkpoint_payload["elapsed_seconds"] >= 0.0


def test_local_worker_failure_returns_recoverable_payload_and_writes_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    def job() -> None:
        raise RuntimeError("boom")

    result = worker.run("case-001", "stage-1", job)

    assert result["status"] == "failed"
    assert result["error"] == "boom"
    assert result["is_recoverable"] is True
    assert result["elapsed_seconds"] >= 0.0
    checkpoint_path = tmp_path / "case-001-stage-1.json"
    assert checkpoint_path.exists()
    checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_payload["status"] == "failed"
    assert checkpoint_payload["error"] == "boom"
    assert checkpoint_payload["is_recoverable"] is True
    assert checkpoint_payload["elapsed_seconds"] >= 0.0


def test_local_worker_run_strict_returns_result_on_success(tmp_path: Path) -> None:
    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    result = worker.run_strict("case-002", "stage-strict-ok", lambda: ["candidate-1", "candidate-2"])

    assert result == ["candidate-1", "candidate-2"]
    checkpoint_path = tmp_path / "case-002-stage-strict-ok.json"
    assert checkpoint_path.exists()
    checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_payload["status"] == "completed"
    assert checkpoint_payload["result"] == ["candidate-1", "candidate-2"]
    assert checkpoint_payload["elapsed_seconds"] >= 0.0


def test_local_worker_run_strict_reraises_and_persists_recoverable_checkpoint(
    tmp_path: Path,
) -> None:
    import pytest

    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    def job() -> None:
        raise RuntimeError("strict boom")

    with pytest.raises(RuntimeError, match="strict boom"):
        worker.run_strict("case-003", "stage-strict-fail", job)

    checkpoint_path = tmp_path / "case-003-stage-strict-fail.json"
    assert checkpoint_path.exists()
    checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_payload["status"] == "failed"
    assert checkpoint_payload["error"] == "strict boom"
    assert checkpoint_payload["is_recoverable"] is True
    assert checkpoint_payload["elapsed_seconds"] >= 0.0


def test_local_worker_run_strict_resumes_from_completed_checkpoint(tmp_path: Path) -> None:
    """When ``resume=True`` and a completed checkpoint already exists, the job
    must not execute again — the stored ``result`` is returned verbatim so the
    pipeline can skip stages that succeeded on a previous attempt (spec §10).
    """
    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    # First run writes the completed checkpoint.
    worker.run_strict("case-004", "cached-stage", lambda: {"value": 42})

    call_count = {"n": 0}

    def job() -> dict:
        call_count["n"] += 1
        return {"value": "different"}

    cached_result = worker.run_strict("case-004", "cached-stage", job, resume=True)

    assert cached_result == {"value": 42}, (
        "Expected the cached result to be returned without calling the job"
    )
    assert call_count["n"] == 0, "Expected cached stage to not re-execute the job"


def test_local_worker_run_strict_reruns_failed_stage_even_with_resume(
    tmp_path: Path,
) -> None:
    """A checkpoint with ``status: failed`` is not a valid resume point — the
    worker must rerun the job so the pipeline can re-attempt a recoverable
    stage after the engineer fixes the underlying cause.
    """
    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    # Seed a failed checkpoint.
    checkpoints.save("case-005", "failed-stage", {"status": "failed", "error": "prev", "is_recoverable": True})

    def job() -> dict:
        return {"value": "fresh-result"}

    result = worker.run_strict("case-005", "failed-stage", job, resume=True)

    assert result == {"value": "fresh-result"}
    checkpoint_payload = json.loads((tmp_path / "case-005-failed-stage.json").read_text(encoding="utf-8"))
    assert checkpoint_payload["status"] == "completed"
    assert checkpoint_payload["result"] == {"value": "fresh-result"}
    assert checkpoint_payload["elapsed_seconds"] >= 0.0
