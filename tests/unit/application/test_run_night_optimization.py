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
