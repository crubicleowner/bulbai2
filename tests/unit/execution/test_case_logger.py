"""Tests for the per-case JSONL stage logger.

Spec §9 mandates ``logs/case.log`` in every case folder. The worker layer
(spec §4.6 "progress publication, failure isolation") is the natural owner
of per-stage entries.
"""
from __future__ import annotations

import json
from pathlib import Path

from bulbopt.execution.logging.case_logger import CaseLogger


def test_case_logger_appends_jsonl_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "case.log"
    logger = CaseLogger(log_path)

    logger.log_stage(stage="prepare_geometry", status="started")
    logger.log_stage(stage="prepare_geometry", status="completed", elapsed_seconds=0.25)

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 2
    assert entries[0]["stage"] == "prepare_geometry"
    assert entries[0]["status"] == "started"
    assert "timestamp" in entries[0]
    assert entries[1]["status"] == "completed"
    assert entries[1]["elapsed_seconds"] == 0.25


def test_case_logger_creates_missing_log_directory(tmp_path: Path) -> None:
    log_path = tmp_path / "nested" / "more" / "logs" / "case.log"
    logger = CaseLogger(log_path)

    logger.log_stage(stage="generate_candidates", status="completed", elapsed_seconds=1.0)

    assert log_path.exists()


def test_case_logger_accepts_extra_context_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "case.log"
    logger = CaseLogger(log_path)

    logger.log_stage(
        stage="evaluate_candidates",
        status="failed",
        elapsed_seconds=0.1,
        extra={"error": "solver outage", "is_recoverable": True},
    )

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert entries[0]["error"] == "solver outage"
    assert entries[0]["is_recoverable"] is True
