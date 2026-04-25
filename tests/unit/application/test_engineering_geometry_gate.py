from __future__ import annotations

import trimesh
import pytest

from bulbopt.application.use_cases.run_night_optimization import (
    _baseline_improvement_summary,
    _engineering_outcome,
    _engineering_valid_candidates,
    _winner_after_baseline_check,
    _mid_gate_evaluator,
    _run_baseline_simple_foam,
    _should_run_baseline_cfd,
    _solver_evidence,
)
from bulbopt.optimization.strategies.cascade_strategy import HighFidelityResult
from bulbopt.optimization.parametric.ffd_deformer import BulbFFDDeformer
from bulbopt.optimization.parametric.kracht_space import KrachtVector


def test_mid_gate_penalizes_coupled_geometry_constraint_violation() -> None:
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    evaluator = _mid_gate_evaluator(
        mesh,
        {"axis_index": 0, "axis_min": 0.0, "axis_max": 2.0},
        BulbFFDDeformer(),
    )
    risky_vector = KrachtVector(
        values={
            "length_ratio": 0.044,
            "breadth_ratio": 0.016,
            "height_ratio": 0.54,
            "axis_z_ratio": 0.25,
            "longitudinal_pos": 0.75,
            "cross_section_c": 0.999,
            "volume_coef": 0.89,
            "nose_sharpness": 0.055,
        }
    )

    row = evaluator([risky_vector])[0]

    assert row == [1e9, 1e9, 1e9]


def test_baseline_improvement_summary_reports_percent_gain() -> None:
    summary = _baseline_improvement_summary(
        baseline_cd=0.395914172090,
        high_fidelity_rows=[
            {"objectives": [0.351003371340, 0.0]},
            {"objectives": [0.324057128630, 0.0]},
        ],
    )

    assert summary["baseline_cd"] == 0.395914172090
    assert summary["winner_cd"] == 0.324057128630
    assert summary["improvement_percent"] == pytest.approx(18.1496517)


def test_run_baseline_simple_foam_parses_openfoam13_cd(tmp_path) -> None:
    stl_path = tmp_path / "baseline.stl"
    stl_path.write_bytes(
        trimesh.exchange.stl.export_stl(trimesh.creation.box(extents=(4.0, 1.5, 1.0)))
    )

    def build_case(case_dir, *, best_candidate_id, best_candidate_geometry_path):
        return {"case_dir": str(case_dir)}

    def run_case(foam_case_dir, *, case_manifest=None, execute=False):
        post_dir = foam_case_dir / "postProcessing" / "forceCoeffs" / "0"
        post_dir.mkdir(parents=True)
        (post_dir / "forceCoeffs.dat").write_text(
            "# Time Cm Cd Cl Cl(f) Cl(r)\n"
            "200 0.0 0.395914172090 0 0 0\n",
            encoding="utf-8",
        )
        return {"status": "executed_ok"}

    result = _run_baseline_simple_foam(
        baseline_work_dir=tmp_path / "baseline_cfd",
        geometry_path=stl_path,
        build_case=build_case,
        run_case=run_case,
    )

    assert result is not None
    assert result["final_cd"] == pytest.approx(0.395914172090)


def test_engineering_valid_candidates_excludes_penalty_and_constraint_violations() -> None:
    valid = HighFidelityResult(
        vector=KrachtVector(
            values={
                "length_ratio": 0.02,
                "breadth_ratio": 0.08,
                "height_ratio": 0.30,
                "axis_z_ratio": 0.20,
                "longitudinal_pos": 0.60,
                "cross_section_c": 0.75,
                "volume_coef": 0.65,
                "nose_sharpness": 0.50,
            }
        ),
        objectives=[0.32, 0.01],
    )
    penalized = HighFidelityResult(
        vector=valid.vector,
        objectives=[1e9, 1e9],
    )
    risky = HighFidelityResult(
        vector=KrachtVector(
            values={
                "length_ratio": 0.044,
                "breadth_ratio": 0.016,
                "height_ratio": 0.54,
                "axis_z_ratio": 0.25,
                "longitudinal_pos": 0.75,
                "cross_section_c": 0.999,
                "volume_coef": 0.89,
                "nose_sharpness": 0.055,
            }
        ),
        objectives=[0.31, 0.01],
    )

    assert _engineering_valid_candidates([penalized, risky, valid]) == [valid]


def test_winner_after_baseline_check_rejects_candidate_worse_than_baseline() -> None:
    assert (
        _winner_after_baseline_check(
            winner_id="candidate-001",
            engineering_summary={
                "baseline_cd": 0.39591417209,
                "winner_cd": 0.69755889307,
                "improvement_percent": -76.1894224,
            },
        )
        is None
    )


def test_winner_after_baseline_check_keeps_candidate_better_than_baseline() -> None:
    assert (
        _winner_after_baseline_check(
            winner_id="candidate-001",
            engineering_summary={
                "baseline_cd": 0.39591417209,
                "winner_cd": 0.32405712863,
                "improvement_percent": 18.1496517,
            },
        )
        == "candidate-001"
    )


def test_engineering_outcome_marks_candidate_worse_than_baseline() -> None:
    outcome = _engineering_outcome(
        winner_id=None,
        engineering_summary={
            "baseline_cd": 0.39591417209,
            "winner_cd": 0.69755889307,
            "improvement_percent": -76.1894224,
        },
    )

    assert outcome == {
        "status": "no_engineering_winner",
        "reason": "candidate_worse_than_baseline",
        "message": "Best CFD candidate is worse than the baseline.",
    }


def test_engineering_outcome_marks_candidate_that_improves_baseline() -> None:
    outcome = _engineering_outcome(
        winner_id="candidate-001",
        engineering_summary={
            "baseline_cd": 0.39591417209,
            "winner_cd": 0.32405712863,
            "improvement_percent": 18.1496517,
        },
    )

    assert outcome["status"] == "engineering_winner"
    assert outcome["reason"] == "improves_baseline"
    assert outcome["winner_id"] == "candidate-001"


def test_engineering_outcome_marks_missing_baseline_as_unverified() -> None:
    outcome = _engineering_outcome(
        winner_id="candidate-001",
        engineering_summary=None,
    )

    assert outcome == {
        "status": "unverified_winner",
        "reason": "baseline_unavailable",
        "winner_id": "candidate-001",
        "message": "Candidate exists, but no baseline CFD comparison is available.",
    }


def test_should_run_baseline_cfd_only_when_valid_high_fidelity_exists() -> None:
    valid = HighFidelityResult(
        vector=KrachtVector(
            values={
                "length_ratio": 0.02,
                "breadth_ratio": 0.08,
                "height_ratio": 0.30,
                "axis_z_ratio": 0.20,
                "longitudinal_pos": 0.60,
                "cross_section_c": 0.75,
                "volume_coef": 0.65,
                "nose_sharpness": 0.50,
            }
        ),
        objectives=[0.32, 0.01],
    )
    penalty = HighFidelityResult(
        vector=valid.vector,
        objectives=[1e9, 1e9],
    )

    assert _should_run_baseline_cfd(openfoam_available=True, high_fidelity_results=[]) is False
    assert _should_run_baseline_cfd(openfoam_available=True, high_fidelity_results=[penalty]) is False
    assert _should_run_baseline_cfd(openfoam_available=True, high_fidelity_results=[valid]) is True
    assert _should_run_baseline_cfd(openfoam_available=False, high_fidelity_results=[valid]) is False


def test_solver_evidence_includes_simple_foam_solver_report() -> None:
    evidence = _solver_evidence(
        {
            "solver_status": "executed_ok",
            "solver_reason": "solver_chain_completed",
            "foam_candidate_id": "candidate-foam",
            "run_manifest": {
                "high_fidelity_used": True,
                "executed_steps": [
                    {"command": ["blockMesh"], "returncode": 0},
                    {
                        "command": ["simpleFoam"],
                        "returncode": 0,
                        "solver_report": {
                            "residuals_available": True,
                            "completed": True,
                            "last_time": 200.0,
                        },
                    },
                ],
            },
        }
    )

    assert evidence["solver_report"]["residuals_available"] is True
    assert evidence["solver_report"]["completed"] is True
    assert evidence["solver_report"]["last_time"] == pytest.approx(200.0)
