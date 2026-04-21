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
    assert checkpoint_payload == {
        "status": "completed",
        "result": {"status": "ok"},
    }


def test_local_worker_failure_returns_recoverable_payload_and_writes_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    def job() -> None:
        raise RuntimeError("boom")

    result = worker.run("case-001", "stage-1", job)

    assert result == {"status": "failed", "error": "boom", "is_recoverable": True}
    checkpoint_path = tmp_path / "case-001-stage-1.json"
    assert checkpoint_path.exists()
    checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_payload == {
        "status": "failed",
        "error": "boom",
        "is_recoverable": True,
    }


def test_local_worker_run_strict_returns_result_on_success(tmp_path: Path) -> None:
    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    result = worker.run_strict("case-002", "stage-strict-ok", lambda: ["candidate-1", "candidate-2"])

    assert result == ["candidate-1", "candidate-2"]
    checkpoint_path = tmp_path / "case-002-stage-strict-ok.json"
    assert checkpoint_path.exists()
    checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_payload == {
        "status": "completed",
        "result": ["candidate-1", "candidate-2"],
    }


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
    assert checkpoint_payload == {
        "status": "failed",
        "error": "strict boom",
        "is_recoverable": True,
    }
