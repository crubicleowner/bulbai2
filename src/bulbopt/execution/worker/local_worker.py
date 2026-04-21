from __future__ import annotations

from typing import Any, Callable

from bulbopt.execution.checkpoints.file_checkpoint_store import FileCheckpointStore


class LocalWorker:
    def __init__(self, checkpoint_store: FileCheckpointStore) -> None:
        self.checkpoint_store = checkpoint_store

    def run(self, case_id: str, stage_name: str, job: Callable[[], Any]) -> Any:
        try:
            result = job()
        except Exception as exc:
            payload = {"status": "failed", "error": str(exc), "is_recoverable": True}
            self.checkpoint_store.save(case_id, stage_name, payload)
            return payload

        payload = {"status": "completed", "result": result}
        self.checkpoint_store.save(case_id, stage_name, payload)
        return result

    def run_strict(self, case_id: str, stage_name: str, job: Callable[[], Any]) -> Any:
        """Run ``job``; persist a recoverable failure checkpoint on error, then re-raise.

        ``run_strict`` is the orchestration variant used by the vertical-slice
        pipeline: each stage produces a ``status: "completed"`` checkpoint on
        success, and a ``status: "failed", is_recoverable: True`` checkpoint
        on failure, but the original exception is re-raised so outer use cases
        can mark the case as failed and roll back cleanly.
        """

        try:
            result = job()
        except Exception as exc:
            payload = {"status": "failed", "error": str(exc), "is_recoverable": True}
            self.checkpoint_store.save(case_id, stage_name, payload)
            raise

        payload = {"status": "completed", "result": result}
        self.checkpoint_store.save(case_id, stage_name, payload)
        return result
