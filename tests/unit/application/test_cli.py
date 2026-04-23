"""Headless CLI entrypoint tests.

Spec §1 lists "overnight unattended runs" as a required mode. The CLI lets
engineers kick off a run without the desktop shell (SSH, CI, batch).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import trimesh

from bulbopt.app.main import run_cli


def _write_valid_stl(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    path.write_bytes(trimesh.exchange.stl.export_stl(mesh))


def test_run_cli_executes_run_subcommand_and_writes_case(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)
    project_root = tmp_path / "projects"

    exit_code = run_cli(
        [
            "run",
            "--source",
            str(source_path),
            "--project",
            str(project_root),
            "--case-name",
            "cli-demo",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "cli-demo" in captured.out
    cases = list(project_root.iterdir())
    assert len(cases) == 1
    case_payload = json.loads((cases[0] / "case.json").read_text(encoding="utf-8"))
    assert case_payload["case_name"] == "cli-demo"
    assert case_payload["status"] in {"completed", "completed_with_warnings"}


def test_run_cli_list_command_prints_case_summaries(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)
    project_root = tmp_path / "projects"

    run_cli(
        [
            "run",
            "--source",
            str(source_path),
            "--project",
            str(project_root),
            "--case-name",
            "first-run",
        ]
    )
    capsys.readouterr()  # drop stdout from the run

    exit_code = run_cli(["list", "--project", str(project_root)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "first-run" in captured.out
    assert "status=" in captured.out


def test_run_cli_resume_command_reuses_checkpoints(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force a mid-pipeline failure, then resume via CLI and verify completion."""
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)
    project_root = tmp_path / "projects"

    from bulbopt.infrastructure.adapters.stub_evaluation import StubEvaluationAdapter

    original = StubEvaluationAdapter.evaluate_candidates

    def boom(self, *args, **kwargs):  # noqa: ARG001
        raise RuntimeError("cli-outage")

    monkeypatch.setattr(StubEvaluationAdapter, "evaluate_candidates", boom)
    exit_code = run_cli(
        [
            "run",
            "--source",
            str(source_path),
            "--project",
            str(project_root),
            "--case-name",
            "resume-cli",
        ]
    )
    assert exit_code != 0  # run failed

    cases = list(project_root.iterdir())
    assert len(cases) == 1
    case_id = cases[0].name

    monkeypatch.setattr(StubEvaluationAdapter, "evaluate_candidates", original)
    capsys.readouterr()

    exit_code = run_cli(["resume", "--project", str(project_root), "--case", case_id])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert case_id in captured.out
    case_payload = json.loads((cases[0] / "case.json").read_text(encoding="utf-8"))
    assert case_payload["status"] in {"completed", "completed_with_warnings"}
    assert case_payload["is_recoverable"] is False


def test_run_cli_night_run_command_writes_pareto_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Smoke test: night-run subcommand flows through to
    run_night_optimization and produces the pareto_front.json artifact."""
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)
    project_root = tmp_path / "projects"

    exit_code = run_cli(
        [
            "night-run",
            "--source", str(source_path),
            "--project", str(project_root),
            "--case-name", "night-cli",
            "--budget-hours", "0.01",
            "--population", "6",
            "--generations", "2",
            "--high-fidelity-budget", "1",
            "--seed", "99",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "night-cli" in captured.out or "case_id=" in captured.out
    # One case in project_root (ignore the .history validity cache the
    # night-run accumulates under <project_root>/.history for the L4
    # classifier across runs).
    cases = [
        p for p in project_root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]
    assert len(cases) == 1
    case_dir = cases[0]
    pareto = case_dir / "working" / "night_optimization" / "pareto_front.json"
    assert pareto.exists()


def test_run_cli_without_arguments_shows_usage_and_returns_nonzero(
    capsys: pytest.CaptureFixture,
) -> None:
    exit_code = run_cli([])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "usage" in (captured.out + captured.err).lower()
