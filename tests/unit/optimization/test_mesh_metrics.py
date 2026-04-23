"""Tests for mesh-quality metric used as the 3rd GA objective.

Design reference: 2026-04-23-bulbopt-mesh-quality-design.md §4 (L2).

``compute_mesh_quality(deformed)`` returns a scalar (lower is better):
    max(dihedral_angle_deviation, symmetry_error, watertight_penalty)
* ``watertight_penalty == 100`` if ``mesh.is_watertight`` is False else 0.
  Broken meshes therefore get dominated by NSGA-II (effectively killed).
"""
from __future__ import annotations

import numpy as np
import pytest
import trimesh

from bulbopt.optimization.quality.mesh_metrics import compute_mesh_quality


def test_watertight_box_mesh_has_low_quality_score() -> None:
    mesh = trimesh.creation.box(extents=(2.0, 1.0, 1.0))
    score = compute_mesh_quality(mesh)
    # Axis-aligned box has perfectly flat faces — dihedral deviation is
    # driven only by the 90-degree corners, and the mesh is symmetric
    # about y=0 if centred.
    assert score < 100.0


def test_broken_mesh_triggers_watertight_penalty() -> None:
    """Remove some faces so watertightness fails. The returned score must
    be >= 100 (watertight penalty) so NSGA-II treats the candidate as
    dominated."""
    mesh = trimesh.creation.box(extents=(2.0, 1.0, 1.0))
    # Drop half the faces to break watertightness.
    broken = trimesh.Trimesh(
        vertices=mesh.vertices.copy(),
        faces=mesh.faces[: len(mesh.faces) // 2].copy(),
        process=False,
    )
    assert broken.is_watertight is False
    score = compute_mesh_quality(broken)
    assert score >= 100.0


def test_quality_score_is_nonnegative_and_finite() -> None:
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    score = compute_mesh_quality(mesh)
    assert np.isfinite(score)
    assert score >= 0.0
