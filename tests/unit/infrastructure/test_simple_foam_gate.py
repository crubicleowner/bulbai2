"""Tests for the simpleFoam high-fidelity gate.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §9.

The gate wraps the existing OpenFOAMAdapter + OpenFOAMRunnerAdapter so
each Kracht vector goes through:

  deform mesh -> write openfoam case with STL -> blockMesh + snappyHexMesh
  -> parse forceCoeffs (or fallback proxy if forceCoeffs unavailable).

Tests inject a fake runner so no real OpenFOAM is invoked.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from bulbopt.infrastructure.adapters.simple_foam_gate import (
    SimpleFoamHighFidelityGate,
)
from bulbopt.optimization.parametric.ffd_deformer import BulbFFDDeformer
from bulbopt.optimization.parametric.kracht_space import (
    KrachtDesignSpace,
    KrachtVector,
)


def _watertight_hull() -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(4.0, 1.5, 1.0))


def _bulb_region(mesh: trimesh.Trimesh) -> dict:
    extents = mesh.extents.astype(float)
    primary = int(np.argmax(extents))
    axis_values = mesh.vertices[:, primary]
    return {
        "axis_index": primary,
        "axis_min": float(axis_values.min()) + float(extents[primary]) * 0.75,
        "axis_max": float(axis_values.max()),
    }


def test_simple_foam_gate_delegates_to_injected_runner_and_returns_drag(
    tmp_path: Path,
) -> None:
    """When the runner reports executed_ok, the gate returns
    [drag_proxy, volume_delta] for each vector."""
    runs: list[dict] = []

    def fake_build(case_dir, *, best_candidate_id, best_candidate_geometry_path):
        runs.append(
            {
                "phase": "build",
                "case_dir": case_dir,
                "best_candidate_id": best_candidate_id,
                "geometry": Path(best_candidate_geometry_path),
            }
        )
        return {"adapter": "openfoam", "available": True, "used": False}

    def fake_run(case_dir, *, case_manifest, execute):
        runs.append({"phase": "run", "case_dir": case_dir, "execute": execute})
        return {
            "status": "executed_ok",
            "reason": "solver_chain_completed",
            "is_recoverable": True,
            "high_fidelity_used": True,
            "executed_steps": [
                {"command": ["blockMesh"], "returncode": 0},
                {"command": ["snappyHexMesh", "-overwrite"], "returncode": 0},
            ],
        }

    gate = SimpleFoamHighFidelityGate(
        work_root=tmp_path,
        baseline_mesh=_watertight_hull(),
        region=_bulb_region(_watertight_hull()),
        deformer=BulbFFDDeformer(),
        build_case=fake_build,
        run_case=fake_run,
    )

    space = KrachtDesignSpace()
    vectors = space.sample(n=2, seed=1)
    objectives = gate.evaluate(vectors)

    assert len(objectives) == 2
    for row in objectives:
        assert len(row) == 2  # [drag_proxy, volume_delta]
        assert row[0] >= 0.0
        assert row[1] >= 0.0
    # Two candidates → 2 build + 2 run invocations.
    assert sum(1 for r in runs if r["phase"] == "build") == 2
    assert sum(1 for r in runs if r["phase"] == "run") == 2
    # Every run must request execute=True so simpleFoam is actually invoked.
    assert all(r["execute"] for r in runs if r["phase"] == "run")


def test_simple_foam_gate_falls_back_on_execution_failure(tmp_path: Path) -> None:
    """When the runner fails (e.g. OpenFOAM missing), the gate must not
    crash the whole night run — it returns a penalty objective so NSGA-II
    continues and the engineer sees the failure in the manifest."""

    def fake_build(case_dir, *, best_candidate_id, best_candidate_geometry_path):
        return {"adapter": "openfoam", "available": False, "used": False}

    def fake_run(case_dir, *, case_manifest, execute):
        return {
            "status": "skipped",
            "reason": "openfoam_unavailable",
            "is_recoverable": True,
            "high_fidelity_used": False,
        }

    gate = SimpleFoamHighFidelityGate(
        work_root=tmp_path,
        baseline_mesh=_watertight_hull(),
        region=_bulb_region(_watertight_hull()),
        deformer=BulbFFDDeformer(),
        build_case=fake_build,
        run_case=fake_run,
    )

    space = KrachtDesignSpace()
    vectors = space.sample(n=1, seed=2)
    objectives = gate.evaluate(vectors)

    assert len(objectives) == 1
    # Fallback is a finite penalty so pymoo doesn't treat it as NaN.
    assert objectives[0][0] >= 1.0
    assert objectives[0][1] >= 0.0


def test_simple_foam_gate_persists_per_candidate_case_dirs(tmp_path: Path) -> None:
    """Each evaluated candidate must get its own case directory so Resume
    can walk through them individually."""
    observed: list[Path] = []

    def fake_build(case_dir, *, best_candidate_id, best_candidate_geometry_path):
        observed.append(Path(case_dir))
        return {"adapter": "openfoam"}

    def fake_run(case_dir, *, case_manifest, execute):
        return {"status": "executed_ok", "is_recoverable": True, "high_fidelity_used": True}

    gate = SimpleFoamHighFidelityGate(
        work_root=tmp_path,
        baseline_mesh=_watertight_hull(),
        region=_bulb_region(_watertight_hull()),
        deformer=BulbFFDDeformer(),
        build_case=fake_build,
        run_case=fake_run,
    )

    vectors = KrachtDesignSpace().sample(n=3, seed=3)
    gate.evaluate(vectors)

    assert len(observed) == 3
    assert len({p.name for p in observed}) == 3  # all distinct
    for candidate_case in observed:
        assert candidate_case.is_dir()
