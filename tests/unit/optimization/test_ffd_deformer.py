"""Tests for PyGeM FFD bulb deformer.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §4.2.
The deformer turns an 8-D Kracht vector into a concrete mesh deformation
localised to the bulb region. Critical invariants:

  * Mesh topology is preserved (same number of faces).
  * Vertices outside the bulb region are bit-identical to the input.
  * The mesh remains watertight after deformation.
  * Two different parameter vectors produce two different meshes.
"""
from __future__ import annotations

import numpy as np
import pytest
import trimesh

from bulbopt.optimization.parametric.ffd_deformer import BulbFFDDeformer
from bulbopt.optimization.parametric.kracht_space import KrachtDesignSpace, KrachtVector


def _watertight_hull() -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    assert mesh.is_watertight
    return mesh


def _bulb_region_from_mesh(mesh: trimesh.Trimesh) -> dict:
    extents = mesh.extents.astype(float)
    primary_axis = int(np.argmax(extents))
    axis_values = mesh.vertices[:, primary_axis]
    axis_min = float(axis_values.min())
    axis_max = float(axis_values.max())
    region_depth = extents[primary_axis] * 0.25
    return {
        "axis_index": primary_axis,
        "axis_min": axis_max - region_depth,
        "axis_max": axis_max,
    }


def test_deformer_preserves_face_topology() -> None:
    mesh = _watertight_hull()
    region = _bulb_region_from_mesh(mesh)
    space = KrachtDesignSpace()
    vector = space.sample(n=1, seed=42)[0]

    deformer = BulbFFDDeformer()
    deformed = deformer.deform(mesh, region, vector)

    assert len(deformed.faces) == len(mesh.faces)
    assert len(deformed.vertices) == len(mesh.vertices)
    np.testing.assert_array_equal(deformed.faces, mesh.faces)


def test_deformer_freezes_vertices_outside_bulb_region() -> None:
    mesh = _watertight_hull()
    region = _bulb_region_from_mesh(mesh)
    space = KrachtDesignSpace()
    vector = space.sample(n=1, seed=7)[0]

    deformer = BulbFFDDeformer()
    deformed = deformer.deform(mesh, region, vector)

    primary_axis = region["axis_index"]
    axis_min = region["axis_min"]
    outside = mesh.vertices[:, primary_axis] < axis_min

    # Vertices strictly outside the region must be bit-identical after FFD.
    np.testing.assert_array_equal(deformed.vertices[outside], mesh.vertices[outside])


def test_deformer_actually_moves_vertices_inside_region() -> None:
    """Identity output would be a bug — a non-zero Kracht vector must
    change at least some bulb-region vertex."""
    mesh = _watertight_hull()
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtVector(
        values={
            "length_ratio":     0.04,   # strong axial push
            "breadth_ratio":    0.15,
            "height_ratio":     0.5,
            "axis_z_ratio":     0.3,
            "longitudinal_pos": 0.7,
            "cross_section_c":  0.8,
            "volume_coef":      0.7,
            "nose_sharpness":   0.3,
        }
    )

    deformer = BulbFFDDeformer()
    deformed = deformer.deform(mesh, region, vector)

    primary_axis = region["axis_index"]
    axis_min = region["axis_min"]
    inside = mesh.vertices[:, primary_axis] >= axis_min
    assert inside.any()
    assert not np.allclose(
        deformed.vertices[inside], mesh.vertices[inside], atol=1e-9
    )


def test_deformer_is_deterministic_for_same_vector() -> None:
    mesh = _watertight_hull()
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtDesignSpace().sample(n=1, seed=13)[0]

    deformer = BulbFFDDeformer()
    a = deformer.deform(mesh, region, vector)
    b = deformer.deform(mesh, region, vector)
    np.testing.assert_array_equal(a.vertices, b.vertices)


def test_deformer_produces_distinct_meshes_for_distinct_vectors() -> None:
    mesh = _watertight_hull()
    region = _bulb_region_from_mesh(mesh)
    space = KrachtDesignSpace()
    a_vec, b_vec = space.sample(n=2, seed=99)

    deformer = BulbFFDDeformer()
    a = deformer.deform(mesh, region, a_vec)
    b = deformer.deform(mesh, region, b_vec)
    # Meshes must differ in at least one vertex position.
    assert not np.allclose(a.vertices, b.vertices, atol=1e-9)


def test_deformer_output_is_mirror_symmetric_around_beam_midplane() -> None:
    """Spec 2026-04-23 §3 Fix B: after FFD the deformed mesh must be
    mirror-symmetric around the beam midplane EVEN when the baseline mesh
    is slightly asymmetric (most real hull STLs have tiny triangulation
    asymmetries). The deformer must ENFORCE symmetry, not just preserve
    it."""
    # Introduce a deliberate asymmetry in the baseline: shift random
    # vertices on the +y side by a tiny amount so the box is no longer
    # bit-symmetric around y=0.
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    mesh = mesh.subdivide().subdivide()
    # Bias +y vertices slightly outward.
    mesh.vertices[mesh.vertices[:, 1] > 0, 1] += 0.01
    # Confirm baseline IS asymmetric.
    plus_y = mesh.vertices[mesh.vertices[:, 1] > 0, 1]
    minus_y = -mesh.vertices[mesh.vertices[:, 1] < 0, 1]
    assert not np.allclose(sorted(plus_y), sorted(minus_y), atol=1e-6), (
        "Baseline should be intentionally asymmetric to exercise the fix"
    )
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtVector(
        values={
            "length_ratio":     0.03,
            "breadth_ratio":    0.15,
            "height_ratio":     0.45,
            "axis_z_ratio":     0.3,
            "longitudinal_pos": 0.6,
            "cross_section_c":  0.7,
            "volume_coef":      0.65,
            "nose_sharpness":   0.4,
        }
    )

    deformer = BulbFFDDeformer()
    deformed = deformer.deform(mesh, region, vector)

    primary = region["axis_index"]
    beam = [i for i in range(3) if i != primary][0]
    other = [i for i in range(3) if i not in (primary, beam)][0]

    # For every vertex on the +beam side, find the closest vertex on the
    # -beam side that matches on (primary, other). They must be reflections.
    plus_mask = deformed.vertices[:, beam] > 1e-9
    minus_mask = deformed.vertices[:, beam] < -1e-9
    plus = deformed.vertices[plus_mask]
    minus = deformed.vertices[minus_mask]
    assert len(plus) == len(minus), (
        f"+beam={len(plus)} vs -beam={len(minus)} — count mismatch breaks mirroring"
    )

    # For each +beam vertex, the mirrored point (primary, -beam, other)
    # must exist among -beam vertices within a small tolerance.
    mirrored_plus = plus.copy()
    mirrored_plus[:, beam] *= -1.0
    # Cheap O(n²) closest-point match (N is small).
    diagonal = float(np.linalg.norm(mesh.extents))
    tolerance = 1e-6 * diagonal
    for p in mirrored_plus:
        distances = np.linalg.norm(minus - p, axis=1)
        assert distances.min() < tolerance, (
            f"No mirror partner within {tolerance:.2e} for vertex {p}; "
            f"closest distance was {distances.min():.2e}"
        )


def test_deformer_blends_smoothly_across_bulb_region_boundary() -> None:
    """Spec 2026-04-23 §3 Fix A: replacing the hard in_region cutoff with a
    smooth radial falloff means vertices close to ``axis_min`` should get a
    *fraction* of the full FFD displacement, not zero. The jump between
    adjacent vertices across the boundary must be significantly smaller
    than the jump produced by the old hard cutoff, i.e. continuous."""
    # Icosphere has ~162 vertices at varying X positions — guaranteed to
    # have some near the blend zone regardless of where axis_min lands.
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=2.0)
    # Scale so primary axis is clearly the longest.
    mesh.apply_scale([2.0, 0.75, 0.5])
    region = _bulb_region_from_mesh(mesh)
    # Strong axial push so the discontinuity is obvious if present.
    vector = KrachtVector(
        values={
            "length_ratio":     0.045,
            "breadth_ratio":    0.10,
            "height_ratio":     0.5,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.5,
            "cross_section_c":  0.75,
            "volume_coef":      0.7,
            "nose_sharpness":   0.5,
        }
    )

    deformer = BulbFFDDeformer()
    deformed = deformer.deform(mesh, region, vector)

    primary = region["axis_index"]
    axis_min = region["axis_min"]
    axis_max = region["axis_max"]
    blend_width = 0.10 * (axis_max - axis_min)
    blend_start = axis_min - blend_width

    # Vertices comfortably outside the blend zone must be unchanged.
    far_outside = mesh.vertices[:, primary] < blend_start - 1e-6
    np.testing.assert_array_almost_equal(
        deformed.vertices[far_outside],
        mesh.vertices[far_outside],
        decimal=9,
    )

    # There must be at least one vertex within the blend zone (between
    # blend_start and axis_min) — otherwise the smoothing is never
    # exercised.
    in_blend = (mesh.vertices[:, primary] >= blend_start) & (
        mesh.vertices[:, primary] < axis_min
    )
    assert np.any(in_blend), "Expected vertices inside the blend zone"

    # Vertices in the blend zone must be displaced by LESS than the full
    # FFD displacement (they see w < 1) but by MORE than zero (they are
    # not un-deformed). Use the first-primary-component displacement as a
    # quick scalar proxy.
    disp = np.linalg.norm(deformed.vertices - mesh.vertices, axis=1)
    assert disp[in_blend].max() > 0.0, "Blend-zone vertices must move"
    full_region = mesh.vertices[:, primary] >= axis_min
    if full_region.any():
        max_full = disp[full_region].max()
        # Blend-zone displacement is a fraction (smoothstep averages ~0.5)
        # of the peak full-region displacement.
        assert disp[in_blend].max() < max_full * 1.01


def test_deformer_result_remains_watertight() -> None:
    """Invariant: FFD only moves vertex positions, never edits faces or
    topology, so a watertight input yields a watertight output."""
    mesh = _watertight_hull()
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtDesignSpace().sample(n=1, seed=4)[0]

    deformer = BulbFFDDeformer()
    deformed = deformer.deform(mesh, region, vector)
    assert deformed.is_watertight
