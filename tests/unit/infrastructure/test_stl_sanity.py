"""Tests for the STL sanity-check adapter.

Design reference: 2026-04-23-bulbopt-mesh-quality-design.md §4 (L6).

``validate_stl`` returns a dict
    {watertight, winding_consistent, volume, vertex_count, face_count,
     checks_passed}
Every top-candidate STL gets its own ``stl_valid.json`` and any failure
surfaces a warning in ``night_report.html``.
"""
from __future__ import annotations

import numpy as np
import pytest
import trimesh

from bulbopt.infrastructure.adapters.stl_sanity import validate_stl


def test_validate_stl_watertight_mesh_all_checks_pass() -> None:
    mesh = trimesh.creation.box(extents=(2.0, 1.0, 1.0))
    report = validate_stl(mesh)
    assert report["watertight"] is True
    assert report["winding_consistent"] is True
    assert report["volume"] > 0
    assert report["vertex_count"] > 0
    assert report["face_count"] > 0
    assert report["checks_passed"] is True


def test_validate_stl_broken_mesh_fails_checks() -> None:
    mesh = trimesh.creation.box(extents=(2.0, 1.0, 1.0))
    broken = trimesh.Trimesh(
        vertices=mesh.vertices.copy(),
        faces=mesh.faces[: len(mesh.faces) // 2].copy(),
        process=False,
    )
    report = validate_stl(broken)
    assert report["watertight"] is False
    # With half the faces removed, volume is ill-defined (not a closed
    # surface), checks_passed must be False so the report can warn.
    assert report["checks_passed"] is False


def test_validate_stl_reports_integer_counts() -> None:
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    report = validate_stl(mesh)
    assert isinstance(report["vertex_count"], int)
    assert isinstance(report["face_count"], int)
    assert report["vertex_count"] == len(mesh.vertices)
    assert report["face_count"] == len(mesh.faces)


def test_validate_stl_volume_zero_marks_failure() -> None:
    """A degenerate (flat) mesh with zero volume should not pass."""
    # Two triangles forming a flat quad in the xy plane — zero volume.
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
    )
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    flat = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    report = validate_stl(flat)
    assert report["checks_passed"] is False
    assert report["volume"] == pytest.approx(0.0, abs=1e-9)
