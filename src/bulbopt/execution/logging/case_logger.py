from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CaseLogger:
    """Append-only JSONL logger for the per-case ``logs/case.log`` file.

    One line per event, newest at the end. Format is stable: timestamp (UTC
    ISO-8601 seconds), stage, status, optional elapsed_seconds, and any
    ``extra`` fields flattened into the record. Engineers can tail or
    jq-pipe the file; the pipeline never blocks on logging because each
    write is an ``open + write + close`` round-trip.
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = Path(log_path)

    def log_stage(
        self,
        *,
        stage: str,
        status: str,
        elapsed_seconds: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stage": stage,
            "status": status,
        }
        if elapsed_seconds is not None:
            record["elapsed_seconds"] = float(elapsed_seconds)
        if extra:
            for key, value in extra.items():
                if key not in record:
                    record[key] = value
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
