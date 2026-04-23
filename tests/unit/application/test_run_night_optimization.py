"""Tests for the ``run_night_optimization`` use case.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §11.

The use case orchestrates the night-run flow:

1. Create case (reuse existing ``create_case``) with ``source_path`` and
   metadata.
2. Run ``prepare_geometry`` once via the existing stub adapter (repair,
   detect bulb region, write repaired.stl and analysis).
3. Build a Kracht-parametric cascade strategy.
4. Persist the Pareto front + high-fidelity results + generation log into
   the case working directory.
5. Return a ``CaseSummary`` pointing at the winning candidate.

Tests use a tiny population / generations and pass mock gates so the
whole run finishes in well under a second.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import trimesh

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.application.use_cases.run_night_optimization import (
    NightOptimizationConfig,
    run_night_optimization,
)
from bulbopt.optimization.parametric.kracht_space import KrachtVector


def _write_watertight_stl(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    path.write_bytes(trimesh.exchange.stl.export_stl(mesh))


def test_run_night_optimization_creates_case_and_writes_pareto_front(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "hull.stl"
    _write_watertight_stl(source_path)

    summary = run_night_optimization(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="night-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
        config=NightOptimizationConfig(
            population=10,
            generations=2,
            high_fidelity_budget=2,
            runtime_budget_hours=1.0,
            seed=42,
            mid_gate_estimated_seconds_per_eval=0.01,
            high_gate_estimated_seconds_per_eval=0.05,
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    pareto_path = case_dir / "working" / "night_optimization" / "pareto_front.json"
    hf_path = case_dir / "working" / "night_optimization" / "high_fidelity_results.json"
    budget_path = case_dir / "working" / "night_optimization" / "budget_trace.json"

    assert summary.status in {"completed", "completed_with_warnings"}
    assert pareto_path.exists()
    assert hf_path.exists()
    assert budget_path.exists()

    pareto = json.loads(pareto_path.read_text(encoding="utf-8"))
    assert "candidates" in pareto
    assert len(pareto["candidates"]) >= 1
    for candidate in pareto["candidates"]:
        assert "vector" in candidate
        assert "objectives" in candidate
        # Vector has all 8 Kracht parameters.
        assert len(candidate["vector"]) == 8

    hf = json.loads(hf_path.read_text(encoding="utf-8"))
    assert "results" in hf
    assert len(hf["results"]) <= 2

    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    assert "trace" in budget
    assert "gate_timings" in budget
    assert "mid" in budget["gate_timings"]


def test_run_night_optimization_summary_points_at_winner(tmp_path: Path) -> None:
    source_path = tmp_path / "hull.stl"
    _write_watertight_stl(source_path)

    summary = run_night_optimization(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="night-winner",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
        config=NightOptimizationConfig(
            population=6,
            generations=2,
            high_fidelity_budget=1,
            runtime_budget_hours=1.0,
            seed=7,
            mid_gate_estimated_seconds_per_eval=0.01,
            high_gate_estimated_seconds_per_eval=0.05,
        ),
    )

    assert summary.best_candidate_id is not None
    case_dir = Path(tmp_path / "projects" / summary.case_id)
    winner_dir = case_dir / "outputs" / "top_candidates" / summary.best_candidate_id
    assert winner_dir.exists()
    assert (winner_dir / "geometry.stl").exists()


def test_run_night_optimization_writes_night_report_html(tmp_path: Path) -> None:
    """Stage 5 renders a Jinja template describing the Pareto front, gate
    timings, and high-fidelity winners."""
    source_path = tmp_path / "hull.stl"
    _write_watertight_stl(source_path)

    summary = run_night_optimization(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="night-report",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
        config=NightOptimizationConfig(
            population=6,
            generations=2,
            high_fidelity_budget=1,
            runtime_budget_hours=1.0,
            seed=13,
            mid_gate_estimated_seconds_per_eval=0.001,
            high_gate_estimated_seconds_per_eval=0.005,
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    report_path = case_dir / "outputs" / "reports" / "night_report.html"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "BulbOpt Night Run" in report_text
    assert "Pareto front" in report_text
    assert "Gate timings" in report_text
    # Report must mention at least one Kracht parameter name.
    assert "length_ratio" in report_text


def test_run_night_optimization_uses_simple_foam_gate_when_openfoam_detected(
    tmp_path: Path, monkeypatch
) -> None:
    """When ``detect_openfoam_available`` returns True, the use case wires
    SimpleFoamHighFidelityGate as the high-fidelity evaluator without
    requiring the caller to pass one. Runs real FFD + case building but
    mocks the OpenFOAM runner so tests stay fast."""
    source_path = tmp_path / "hull.stl"
    _write_watertight_stl(source_path)

    # Force detection True at the import site used by the use case, and
    # mock the runner to return executed_ok.
    from bulbopt.application.use_cases import run_night_optimization as use_case_module
    from bulbopt.infrastructure.adapters import openfoam_runner

    monkeypatch.setattr(
        use_case_module, "detect_openfoam_available", lambda: True
    )

    run_calls: list[dict] = []

    def fake_run(self, case_dir, *, case_manifest=None, execute=False, timeout_seconds=600):
        run_calls.append({"case_dir": case_dir, "execute": execute})
        return {
            "status": "executed_ok",
            "is_recoverable": True,
            "high_fidelity_used": True,
            "executed_steps": [],
        }

    monkeypatch.setattr(
        openfoam_runner.OpenFOAMRunnerAdapter,
        "run_case",
        fake_run,
    )

    summary = run_night_optimization(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="night-foam",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
        config=NightOptimizationConfig(
            population=5,
            generations=2,
            high_fidelity_budget=2,
            runtime_budget_hours=1.0,
            seed=3,
            mid_gate_estimated_seconds_per_eval=0.001,
            high_gate_estimated_seconds_per_eval=0.005,
        ),
    )

    assert summary.status in {"completed", "completed_with_warnings"}
    # At least one high-fidelity run was invoked through the real gate.
    assert len(run_calls) >= 1
    assert all(call["execute"] for call in run_calls)


def test_run_night_optimization_persists_case_json_with_recoverable_flag(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "hull.stl"
    _write_watertight_stl(source_path)

    summary = run_night_optimization(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="night-resumable",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
        config=NightOptimizationConfig(
            population=5,
            generations=2,
            high_fidelity_budget=1,
            runtime_budget_hours=1.0,
            seed=1,
            mid_gate_estimated_seconds_per_eval=0.001,
            high_gate_estimated_seconds_per_eval=0.005,
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert payload["status"] in {"completed", "completed_with_warnings"}
    assert payload["is_recoverable"] is False


def test_run_night_optimization_writes_stl_sanity_json(tmp_path: Path) -> None:
    """L6: every top-candidate STL gets a companion stl_valid.json with
    watertight / winding / volume / counts / checks_passed."""
    source_path = tmp_path / "hull.stl"
    _write_watertight_stl(source_path)

    summary = run_night_optimization(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="night-sanity",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
        config=NightOptimizationConfig(
            population=5,
            generations=2,
            high_fidelity_budget=2,
            runtime_budget_hours=1.0,
            seed=101,
            mid_gate_estimated_seconds_per_eval=0.001,
            high_gate_estimated_seconds_per_eval=0.005,
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    winner_dir = case_dir / "outputs" / "top_candidates" / summary.best_candidate_id
    sanity_path = winner_dir / "stl_valid.json"
    assert sanity_path.exists()
    report = json.loads(sanity_path.read_text(encoding="utf-8"))
    for key in (
        "watertight",
        "winding_consistent",
        "volume",
        "vertex_count",
        "face_count",
        "checks_passed",
    ):
        assert key in report


def test_run_night_optimization_writes_history_jsonl(tmp_path: Path) -> None:
    """L1: every high-fidelity (vector, cd) pair must be persisted to the
    history JSONL so future runs can warm-start from it."""
    source_path = tmp_path / "hull.stl"
    _write_watertight_stl(source_path)
    history_path = tmp_path / "history" / "history.jsonl"

    run_night_optimization(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="night-history",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
        config=NightOptimizationConfig(
            population=5,
            generations=2,
            high_fidelity_budget=2,
            runtime_budget_hours=1.0,
            seed=42,
            mid_gate_estimated_seconds_per_eval=0.001,
            high_gate_estimated_seconds_per_eval=0.005,
            history_path=history_path,
        ),
    )

    assert history_path.exists()
    rows = [
        json.loads(line)
        for line in history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # At least one high-fidelity row was appended.
    assert len(rows) >= 1
    for row in rows:
        assert "parameters" in row and "cd" in row
        assert "length_ratio" in row["parameters"]


def test_run_night_optimization_warm_starts_from_history(tmp_path: Path) -> None:
    """L1: a second run with a populated history places the top historical
    vectors into the initial NSGA-II population."""
    from bulbopt.application.use_cases import run_night_optimization as use_case_module
    from bulbopt.optimization.strategies import nsga2_strategy as strategy_module

    source_path = tmp_path / "hull.stl"
    _write_watertight_stl(source_path)
    history_path = tmp_path / "history.jsonl"

    # Run 1 — populate the history.
    run_night_optimization(
        project_root=tmp_path / "projects1",
        command=CreateCaseCommand(
            case_name="night-run-one",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
        config=NightOptimizationConfig(
            population=5,
            generations=2,
            high_fidelity_budget=2,
            runtime_budget_hours=1.0,
            seed=1,
            mid_gate_estimated_seconds_per_eval=0.001,
            high_gate_estimated_seconds_per_eval=0.005,
            history_path=history_path,
        ),
    )
    # Sanity: history populated before run 2.
    rows_after_run1 = history_path.read_text(encoding="utf-8").splitlines()
    assert len(rows_after_run1) >= 1

    # Run 2 — capture the initial population by monkeypatching
    # NSGA2Strategy.optimize to record vectors passed by the sampling.
    captured: list[list[float]] = []
    original_build = strategy_module._build_initial_sampling

    def spy_build(**kwargs):
        array = original_build(**kwargs)
        for row in array:
            captured.append([float(x) for x in row])
        return array

    import unittest.mock as _mock

    with _mock.patch.object(
        strategy_module, "_build_initial_sampling", side_effect=spy_build
    ):
        run_night_optimization(
            project_root=tmp_path / "projects2",
            command=CreateCaseCommand(
                case_name="night-run-two",
                source_path=str(source_path),
                vessel_length_m=142.0,
                vessel_beam_m=19.1,
                vessel_draft_m=6.0,
                displacement_t=8420.0,
                speed_knots=[18.0, 20.0],
            ),
            config=NightOptimizationConfig(
                population=5,
                generations=2,
                high_fidelity_budget=2,
                runtime_budget_hours=1.0,
                seed=2,
                mid_gate_estimated_seconds_per_eval=0.001,
                high_gate_estimated_seconds_per_eval=0.005,
                history_path=history_path,
            ),
        )

    # Warm-start path was taken — the spy was called at least once.
    assert len(captured) > 0
