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
