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


def test_compute_mesh_quality_respects_beam_axis_kwarg() -> None:
    """The default ``argmin(extents)`` heuristic picks the wrong beam axis
    on a real ship hull (audit 2026-04-26): on docs/base_hull.stl the Y
    extent is slightly smaller than Z, so the metric mirrors around Y
    (the asymmetric draft axis) instead of Z (the symmetric beam axis).
    When ``beam_axis`` is supplied explicitly, the metric must use it.

    Use a smooth icosphere (low dihedral deviation so the symmetry
    component dominates ``max(...)``) and squash its lower half so Y is
    teardrop-asymmetric while Z stays a perfect mirror."""
    base = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    verts = np.asarray(base.vertices, dtype=float).copy()
    verts[:, 0] *= 4.0           # primary = X
    # Z stays at unit radius (symmetric ±1, beam axis).
    # Squash the bottom (-Y) so the Y distribution is teardrop-shaped:
    # vertices with Y < 0 are pulled toward the centerline.
    verts[verts[:, 1] < 0, 1] *= 0.3
    mesh = trimesh.Trimesh(vertices=verts, faces=base.faces, process=False)

    score_z = compute_mesh_quality(mesh, beam_axis=2)
    score_y = compute_mesh_quality(mesh, beam_axis=1)

    assert score_z < score_y, (
        f"beam_axis kwarg ignored: Z-quality {score_z:.6f} should be smaller "
        f"than Y-quality {score_y:.6f} on a Z-symmetric, Y-teardrop hull"
    )
