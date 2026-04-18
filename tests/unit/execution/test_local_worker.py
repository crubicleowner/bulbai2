from __future__ import annotations

from pathlib import Path

from bulbopt.execution.worker.local_worker import LocalWorker


def test_local_worker_success_returns_job_result_and_writes_checkpoint(tmp_path: Path) -> None:
    worker_root = tmp_path / "case-001"
    worker = LocalWorker(root_dir=worker_root)

    result = worker.run("case-001", "stage-1", lambda: {"status": "ok"})

    assert result == {"status": "ok"}
    checkpoint_path = worker_root / "working" / "checkpoints" / "case-001-stage-1.json"
    assert checkpoint_path.exists()
    assert checkpoint_path.read_text(encoding="utf-8").strip() == (
        '{\n'
        '  "status": "completed",\n'
        '  "result": {\n'
        '    "status": "ok"\n'
        '  }\n'
        '}'
    )


def test_local_worker_failure_returns_recoverable_payload_and_writes_checkpoint(
    tmp_path: Path,
) -> None:
    worker_root = tmp_path / "case-001"
    worker = LocalWorker(root_dir=worker_root)

    def job() -> None:
        raise RuntimeError("boom")

    result = worker.run("case-001", "stage-1", job)

    assert result == {"status": "failed", "error": "boom", "is_recoverable": True}
    checkpoint_path = worker_root / "working" / "checkpoints" / "case-001-stage-1.json"
    assert checkpoint_path.exists()
    assert checkpoint_path.read_text(encoding="utf-8").strip() == (
        '{\n'
        '  "status": "failed",\n'
        '  "error": "boom",\n'
        '  "is_recoverable": true\n'
        '}'
    )
