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

    # Invariant only holds when adaptive subdivision is disabled — with
    # the L5 hook active the baseline's 12-face box gets densified to
    # ~500 region tris, so topology legitimately changes.
    deformer = BulbFFDDeformer(adaptive_subdivision=False)
    deformed = deformer.deform(mesh, region, vector)

    assert len(deformed.faces) == len(mesh.faces)
    assert len(deformed.vertices) == len(mesh.vertices)
    np.testing.assert_array_equal(deformed.faces, mesh.faces)


def test_deformer_freezes_vertices_outside_bulb_region() -> None:
    mesh = _watertight_hull()
    region = _bulb_region_from_mesh(mesh)
    space = KrachtDesignSpace()
    vector = space.sample(n=1, seed=7)[0]

    # Vertex-index invariant only holds when subdivision is off.
    deformer = BulbFFDDeformer(adaptive_subdivision=False)
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

    # Subdivision off so the vertex-index mask carries over unchanged.
    deformer = BulbFFDDeformer(adaptive_subdivision=False)
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
    more mirror-symmetric with ``force_port_starboard_symmetry=True``
    than without it, AND must not damage the mesh (volume preserved
    within ~5%). The safety guards (mutual pairing + distance threshold)
    may decline to pair some vertices when the baseline is badly
    asymmetric; that's intentionally safer than folding the mesh."""
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    mesh = mesh.subdivide().subdivide()
    # Small jitter on +y vertices so the baseline is slightly asymmetric.
    mesh.vertices[mesh.vertices[:, 1] > 0, 1] += 0.001
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

    # Compare WITH vs WITHOUT symmetry enforcement on the same baseline.
    # The fix must produce a significantly better mirror RMS in the
    # bulb region, without requiring absolute symmetry for vertices the
    # safety guards (mutual pairing + distance threshold) refuse to
    # touch.
    without_deformer = BulbFFDDeformer(force_port_starboard_symmetry=False)
    with_deformer = BulbFFDDeformer(force_port_starboard_symmetry=True)
    without = without_deformer.deform(mesh, region, vector)
    with_sym = with_deformer.deform(mesh, region, vector)

    primary = region["axis_index"]
    beam = [i for i in range(3) if i != primary][0]
    axis_min = region["axis_min"]
    axis_max = region["axis_max"]
    blend_start = axis_min - 0.10 * (axis_max - axis_min)

    def mirror_rms_in_region(deformed: trimesh.Trimesh) -> float:
        v = np.asarray(deformed.vertices, dtype=float)
        in_region = v[:, primary] >= blend_start
        pts = v[in_region]
        if len(pts) == 0:
            return 0.0
        mirrors = pts.copy()
        mirrors[:, beam] *= -1.0
        diff = mirrors[:, None, :] - pts[None, :, :]
        d = np.linalg.norm(diff, axis=2).min(axis=1)
        return float(np.sqrt(np.mean(d ** 2)))

    rms_without = mirror_rms_in_region(without)
    rms_with = mirror_rms_in_region(with_sym)
    assert rms_with < rms_without, (
        f"Symmetry enforcement did not improve mirror RMS at all: "
        f"{rms_without:.6f} → {rms_with:.6f}"
    )
    # Volume must not drift more than 5% — the safety guards are what
    # prevent the 30% folding regression seen in the first implementation.
    vol_without = abs(without.volume)
    vol_with = abs(with_sym.volume)
    drift = abs(vol_with - vol_without) / max(vol_without, 1e-9)
    assert drift < 0.05, (
        f"Symmetry enforcement caused {drift*100:.1f}% volume drift "
        f"(threshold 5%) — algorithm folding the mesh"
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

    # Subdivision off so the vertex-index mask carries over unchanged.
    deformer = BulbFFDDeformer(adaptive_subdivision=False)
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


def test_deformer_taubin_smoothing_preserves_volume_within_one_percent() -> None:
    """Spec 2026-04-23 §3 Fix C: Taubin smoothing rounds the sharp facet
    edges without shrinking the mesh (unlike plain Laplacian). Volume
    drift after 3 iterations must stay within ±1% of the un-smoothed
    FFD output."""
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    mesh.apply_scale([2.0, 0.75, 0.5])
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtVector(
        values={
            "length_ratio":     0.03,
            "breadth_ratio":    0.12,
            "height_ratio":     0.4,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.55,
            "cross_section_c":  0.7,
            "volume_coef":      0.6,
            "nose_sharpness":   0.4,
        }
    )

    deformer_raw = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=0,
    )
    deformer_smoothed = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=3,
    )
    raw = deformer_raw.deform(mesh, region, vector)
    smoothed = deformer_smoothed.deform(mesh, region, vector)

    # Volume drift must be small.
    raw_volume = abs(raw.volume)
    smoothed_volume = abs(smoothed.volume)
    drift = abs(smoothed_volume - raw_volume) / max(raw_volume, 1e-12)
    assert drift < 0.01, (
        f"Taubin drift {drift*100:.2f}% exceeds 1% budget "
        f"(raw_volume={raw_volume:.3f}, smoothed_volume={smoothed_volume:.3f})"
    )

    # Smoothed vertices must actually be different from raw.
    diff = np.linalg.norm(smoothed.vertices - raw.vertices, axis=1)
    assert diff.max() > 1e-6, "Expected Taubin to move at least one vertex"

    # Smoothed mesh stays watertight.
    assert smoothed.is_watertight


def test_deformer_result_remains_watertight() -> None:
    """Invariant: FFD only moves vertex positions, never edits faces or
    topology, so a watertight input yields a watertight output."""
    mesh = _watertight_hull()
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtDesignSpace().sample(n=1, seed=4)[0]

    deformer = BulbFFDDeformer()
    deformed = deformer.deform(mesh, region, vector)
    assert deformed.is_watertight


def _vertex_duplicated_hull() -> trimesh.Trimesh:
    """Synthesise an icosphere with each face's three vertices unique
    (3x vertex count, no sharing) — the pathological layout produced by
    trimesh.load on an STL without an explicit merge_vertices call,
    which Agent 1 diagnosed as the root cause of -99% volume Taubin
    collapse."""
    base = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    base.apply_scale([2.0, 0.75, 0.5])
    # Expand: create new vertex array with 3× the entries, rewrite faces.
    new_vertices = base.vertices[base.faces.reshape(-1)]
    new_faces = np.arange(len(new_vertices), dtype=np.int64).reshape(-1, 3)
    duplicated = trimesh.Trimesh(
        vertices=new_vertices,
        faces=new_faces,
        process=False,
    )
    # Baseline sanity: this mesh is unshared (3×V == 3×F).
    assert len(duplicated.vertices) == 3 * len(base.faces)
    return duplicated


def test_taubin_does_not_collapse_mesh_with_duplicated_vertices() -> None:
    """F1 regression: the real docs/base_hull.stl has 3 vertices per
    face with zero index-sharing. Before the fix, Taubin ran on a
    degree-2 graph and collapsed the mesh by -99% volume. After welding
    by position the smoothing operates on the real topology."""
    mesh = _vertex_duplicated_hull()
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtVector(
        values={
            "length_ratio":     0.03,
            "breadth_ratio":    0.12,
            "height_ratio":     0.4,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.55,
            "cross_section_c":  0.7,
            "volume_coef":      0.6,
            "nose_sharpness":   0.4,
        }
    )
    # Subdivision is irrelevant here — we're testing Taubin on unshared topology.
    deformer_raw = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=0,
        adaptive_subdivision=False,
    )
    deformer_smoothed = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=3,
        adaptive_subdivision=False,
    )
    raw = deformer_raw.deform(mesh, region, vector)
    smoothed = deformer_smoothed.deform(mesh, region, vector)

    raw_volume = float(abs(raw.volume))
    smoothed_volume = float(abs(smoothed.volume))
    drift = abs(smoothed_volume - raw_volume) / max(raw_volume, 1e-12)
    # The disconnected-graph bug produced drifts >50% — anything under
    # 5% proves the welded Laplacian is doing the right thing on an
    # STL-pathological mesh.
    assert drift < 0.05, (
        f"Welded Taubin collapsed volume by {drift*100:.1f}% "
        f"(raw={raw_volume:.3f}, smoothed={smoothed_volume:.3f})"
    )


def test_symmetry_does_not_snap_off_centerline_vertices_to_zero() -> None:
    """F3 regression: the self-pair branch used to pin any vertex with
    no mirror partner to beam=0, which collapsed the bottom flange
    (113 vertices with |beam| up to 0.60 m). After the fix, self-paired
    vertices farther than the mirror threshold from the centerline keep
    their original beam coordinate."""
    mesh = _watertight_hull()
    # Nudge every +y vertex so some have no natural mirror pair in the
    # mesh — they will self-pair in the kd-tree query.
    mesh = mesh.subdivide().subdivide()
    mesh.vertices[mesh.vertices[:, 1] > 0.3, 1] += 0.2
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtVector(
        values={
            "length_ratio":     0.03,
            "breadth_ratio":    0.1,
            "height_ratio":     0.4,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.5,
            "cross_section_c":  0.7,
            "volume_coef":      0.6,
            "nose_sharpness":   0.4,
        }
    )
    deformer = BulbFFDDeformer(
        force_port_starboard_symmetry=True,
        post_smoothing_iterations=0,
        adaptive_subdivision=False,
    )
    deformed = deformer.deform(mesh, region, vector)

    primary = region["axis_index"]
    beam = [i for i in range(3) if i != primary][0]
    in_region = mesh.vertices[:, primary] >= region["axis_min"]
    # Count off-centerline vertices (|y| > 0.3) that were at |y| > 0.3
    # before deformation and are now flat at beam=0. A correct symmetry
    # pass must leave them alone when they have no real mirror.
    originally_off = (np.abs(mesh.vertices[:, beam]) > 0.3) & in_region
    collapsed_to_zero = np.abs(deformed.vertices[originally_off, beam]) < 1e-6
    # Before the fix, many of these got snapped to zero. After the fix,
    # none of them should.
    assert not collapsed_to_zero.any(), (
        f"Symmetry snapped {int(collapsed_to_zero.sum())} off-centerline "
        f"vertices to beam=0 — F3 regression"
    )


def test_ffd_amplitude_clamp_prevents_triangle_inversion() -> None:
    """F5 regression: the high-``longitudinal_pos`` + low-``nose_sharpness``
    corner of Kracht space used to produce 66–76 flipped triangles in
    the nose tip. After clamping per-lattice-point offset to half the
    cell spacing, the deformed mesh must keep ≥99% of its faces with
    their original orientation."""
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    mesh.apply_scale([2.0, 0.75, 0.5])
    region = _bulb_region_from_mesh(mesh)
    # Extreme adversarial vector: push length to max, sharpen the nose.
    vector = KrachtVector(
        values={
            "length_ratio":     0.05,
            "breadth_ratio":    0.15,
            "height_ratio":     0.5,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.95,
            "cross_section_c":  0.7,
            "volume_coef":      0.9,
            "nose_sharpness":   0.05,
        }
    )
    deformer = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=0,
        adaptive_subdivision=False,
    )
    original = mesh
    deformed = deformer.deform(mesh, region, vector)

    # Face orientation proxy: sign of the scalar triple product of face
    # edge vectors against the centroid-outward direction. A flipped
    # face has the opposite sign from the baseline.
    def face_orientations(m: trimesh.Trimesh) -> np.ndarray:
        tri = m.vertices[m.faces]
        a = tri[:, 1] - tri[:, 0]
        b = tri[:, 2] - tri[:, 0]
        normal = np.cross(a, b)
        centroid = tri.mean(axis=1)
        outward = centroid - m.centroid
        # Positive when the normal points outward.
        return np.sign(np.einsum("ij,ij->i", normal, outward))

    orig_signs = face_orientations(original)
    defo_signs = face_orientations(deformed)
    flipped = (orig_signs * defo_signs) < 0.0
    flip_ratio = float(flipped.sum()) / float(max(len(defo_signs), 1))
    assert flip_ratio < 0.01, (
        f"FFD clamp failed: {flip_ratio*100:.2f}% of faces flipped "
        f"({int(flipped.sum())}/{len(defo_signs)})"
    )


# ---- Beam-axis detection regression tests ---------------------------------
#
# Today (audit found 2026-04-26): both ``BulbFFDDeformer`` and
# ``compute_mesh_quality`` pick the beam axis from the *non-primary* axes
# using a heuristic (``other_axes[0]`` / ``argmin(extents)``) that is wrong
# for real ship hulls where the asymmetric draft axis happens to be Y and
# the symmetric port-starboard beam axis is Z. The fix: detect the beam
# axis from the actual mesh symmetry — the non-primary axis whose vertex
# distribution is most centered around zero — and persist it in the region
# dict so all downstream consumers use the correct axis.


def _ship_like_hull_z_beam() -> trimesh.Trimesh:
    """Synthesise a ship-shaped mesh with primary=X (longest), beam=Z
    (symmetric ±a around 0) and draft=Y (asymmetric, range [-1, +5]).

    This mirrors the docs/base_hull.stl layout exactly: X is the
    bow-stern length, Y is the keel-to-deck draft (asymmetric because
    waterline is well above the bottom), Z is the port-starboard beam
    (symmetric about the centerline).

    Y has a *larger* extent than Z deliberately — so the old
    ``argmin(extents)`` mesh-quality heuristic also picks the wrong axis.
    """
    # Long, low-aspect box so X is unambiguously the primary axis.
    mesh = trimesh.creation.box(extents=(20.0, 6.0, 2.0))
    # Subdivide so the deformer has enough vertices in the bulb region
    # to exercise the FFD lattice meaningfully.
    mesh = mesh.subdivide().subdivide().subdivide()
    # Translate Y by +2 → range [-1, +5] (asymmetric, draft-like).
    # Z stays in [-1, +1] (symmetric, beam-like).
    mesh.vertices[:, 1] += 2.0
    return mesh


def _region_with_beam_detection(mesh: trimesh.Trimesh) -> dict:
    """Build a region dict the same way StubGeometryAdapter does, so the
    beam_axis detection logic is exercised end-to-end."""
    from bulbopt.infrastructure.adapters.stub_geometry import StubGeometryAdapter
    adapter = StubGeometryAdapter()
    analysis = adapter._build_geometry_analysis(
        mesh,
        repaired_path=None,  # type: ignore[arg-type]
    )
    return analysis["bulb_region"]


def test_beam_axis_picks_z_on_real_ship_hull() -> None:
    """The repaired-mesh analysis must detect Z as the beam axis when the
    hull is symmetric in Z and asymmetric in Y, even though both Y and Z
    are non-primary and Y has slightly smaller extent."""
    mesh = _ship_like_hull_z_beam()
    region = _region_with_beam_detection(mesh)
    assert region["axis_index"] == 0  # primary = X
    assert region["beam_axis"] == 2, (
        f"Expected beam_axis=2 (Z, port-starboard) on a Z-symmetric hull, "
        f"got beam_axis={region['beam_axis']} (this is the audit bug)"
    )
    assert region["draft_axis"] == 1


def test_breadth_ratio_actually_deforms_beam_direction() -> None:
    """A high ``breadth_ratio`` Kracht push must grow the Z-extent
    (port-starboard beam) on a Z-symmetric hull — not the Y-extent (draft).
    Today this fails because the deformer hard-codes beam=other_axes[0]=Y."""
    mesh = _ship_like_hull_z_beam()
    region = _region_with_beam_detection(mesh)
    # Use the forward 25% of the hull as the bulb region — same fraction
    # the production code applies in StubGeometryAdapter.
    axis_max = float(mesh.vertices[:, 0].max())
    extent = float(mesh.extents[0])
    region["axis_min"] = axis_max - 0.25 * extent
    region["axis_max"] = axis_max

    # Vector: only ``breadth_ratio`` is non-neutral. ``nose_sharpness=1.0``
    # zeroes the corner taper that would otherwise leak into the draft
    # axis, ``cross_section_c=0.5`` and ``axis_z_ratio=0.25`` are at the
    # neutral midpoints, and length / height are zero. This isolates
    # breadth as the only knob actively pushing.
    vector = KrachtVector(
        values={
            "length_ratio":     0.0,
            "breadth_ratio":    0.15,   # strong beam push
            "height_ratio":     0.0,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.5,
            "cross_section_c":  0.5,
            "volume_coef":      0.5,
            "nose_sharpness":   1.0,
        }
    )
    deformer = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=0,
        adaptive_subdivision=False,
    )
    deformed = deformer.deform(mesh, region, vector)

    before = mesh.extents
    after = deformed.extents
    z_growth = (after[2] - before[2]) / max(before[2], 1e-9)
    y_growth = (after[1] - before[1]) / max(before[1], 1e-9)

    assert z_growth > 0.05, (
        f"breadth_ratio failed to grow Z-extent: "
        f"before {before[2]:.4f} → after {after[2]:.4f} (Δ={z_growth*100:.2f}%)"
    )
    assert y_growth < 0.01, (
        f"breadth_ratio leaked into Y (draft) direction: "
        f"before {before[1]:.4f} → after {after[1]:.4f} (Δ={y_growth*100:.2f}%) "
        f"— this is the audit bug"
    )


def test_mirror_symmetry_acts_on_correct_axis() -> None:
    """``force_port_starboard_symmetry=True`` must mirror around Z (the
    truly symmetric axis) when the region dict carries beam_axis=2, even
    if a Z-asymmetric Kracht vector is applied. Y-extent must be preserved
    exactly because the mirror pass shouldn't touch Y."""
    mesh = _ship_like_hull_z_beam()
    region = _region_with_beam_detection(mesh)
    axis_max = float(mesh.vertices[:, 0].max())
    extent = float(mesh.extents[0])
    region["axis_min"] = axis_max - 0.25 * extent
    region["axis_max"] = axis_max

    # Same isolation as the breadth-only test: nose_sharpness=1.0 zeros
    # the corner taper so we can attribute every Y-extent change purely
    # to the symmetry pass.
    vector = KrachtVector(
        values={
            "length_ratio":     0.0,
            "breadth_ratio":    0.15,   # asymmetric in Z, but breadth pushes ±Z
            "height_ratio":     0.0,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.5,
            "cross_section_c":  0.5,
            "volume_coef":      0.5,
            "nose_sharpness":   1.0,
        }
    )
    y_extent_before = float(mesh.extents[1])

    deformer = BulbFFDDeformer(
        force_port_starboard_symmetry=True,
        post_smoothing_iterations=0,
        adaptive_subdivision=False,
    )
    deformed = deformer.deform(mesh, region, vector)

    # Z-mirror RMS error: vertices must be symmetric around Z=0 within the
    # bulb region (small fraction of beam extent).
    v = np.asarray(deformed.vertices, dtype=float)
    in_region = v[:, 0] >= region["axis_min"]
    pts = v[in_region]
    mirrors = pts.copy()
    mirrors[:, 2] *= -1.0
    diff = mirrors[:, None, :] - pts[None, :, :]
    d = np.linalg.norm(diff, axis=2).min(axis=1)
    rms = float(np.sqrt(np.mean(d ** 2)))
    beam_extent = float(deformed.extents[2])
    assert rms < 1e-3 * beam_extent, (
        f"Z-mirror RMS={rms:.6f} exceeds 1e-3 of beam extent {beam_extent:.4f} "
        f"— mirror pass acted on the wrong axis"
    )

    # Y-extent must be identical to the input (within float noise).
    y_extent_after = float(deformed.extents[1])
    assert abs(y_extent_after - y_extent_before) < 1e-6 * y_extent_before, (
        f"Y-extent (draft) changed during port-starboard symmetry pass: "
        f"{y_extent_before:.6f} → {y_extent_after:.6f} — this is the audit bug"
    )


# ---- Bug #6 + Bug #8 regression tests -------------------------------------
#
# Audit 2026-04-26: two robustness defects in the post-FFD Taubin smoother:
#
#   #6  When the bulb region has very few participating vertices (≲30), the
#       welded Laplacian is built on a graph with degree-1 boundary nodes.
#       Taubin's noise then propagates past the smoothstep taper and
#       produces non-manifold (non-watertight) output. Fix: skip Taubin
#       entirely when n_unique < 60 OR len(participating) < 30.
#
#   #8  ``np.round(decimals=6)`` welds positions to 1e-6 — fine for meters
#       but well below float precision for mm-scale STLs. Fix: derive an
#       adaptive ``decimals`` from the mesh's bounding-box diagonal so
#       coincident vertices are welded at any hull scale.


def _tiny_bulb_region_mesh() -> trimesh.Trimesh:
    """Subdivisions=1 icosphere has 42 unique vertices and only ~13 of
    them sit in a 25 % bulb region. That's well below the Bug #6 guard
    thresholds, so the Taubin pass must be skipped on this mesh."""
    mesh = trimesh.creation.icosphere(subdivisions=1, radius=1.0)
    mesh.apply_scale([2.0, 0.75, 0.5])
    return mesh


def test_taubin_guard_skips_when_region_too_small() -> None:
    """Bug #6: a tight bulb region (<30 participating vertices and/or <60
    welded mesh nodes) used to feed an ill-conditioned graph into Taubin
    and could break watertightness. After the guard, smoothing is
    bypassed but the FFD displacement still applies — the mesh stays
    watertight, just slightly more polygonal."""
    mesh = _tiny_bulb_region_mesh()
    region = _bulb_region_from_mesh(mesh)
    # Sanity check the test mesh actually exercises the small-region path.
    primary = region["axis_index"]
    blend_width = 0.10 * (region["axis_max"] - region["axis_min"])
    blend_start = region["axis_min"] - blend_width
    participating = mesh.vertices[:, primary] >= blend_start
    n_participating = int(participating.sum())
    n_unique = int(np.unique(np.round(mesh.vertices, decimals=6), axis=0).shape[0])
    assert n_participating < 30 or n_unique < 60, (
        f"Test mesh too large to exercise the small-region guard: "
        f"participating={n_participating}, n_unique={n_unique}"
    )

    vector = KrachtVector(
        values={
            "length_ratio":     0.03,
            "breadth_ratio":    0.12,
            "height_ratio":     0.4,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.55,
            "cross_section_c":  0.7,
            "volume_coef":      0.6,
            "nose_sharpness":   0.4,
        }
    )

    deformer = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=3,
        adaptive_subdivision=False,
    )
    deformed = deformer.deform(mesh, region, vector)

    # Watertightness preserved despite Taubin being skipped.
    assert deformed.is_watertight, (
        "Bug #6: small-region guard should keep mesh watertight"
    )

    # FFD displacement actually applied — bulb-region vertices moved.
    inside = mesh.vertices[:, primary] >= region["axis_min"]
    assert inside.any(), "Test mesh has no vertices inside the bulb region"
    assert not np.allclose(
        deformed.vertices[inside], mesh.vertices[inside], atol=1e-9
    ), "Guard should NOT disable FFD; only Taubin smoothing"

    # When Taubin is skipped, the output must equal the no-smoothing output
    # (i.e. ``post_smoothing_iterations=0``). This pins down that the guard
    # truly bypassed Taubin rather than just softened it.
    deformer_no_smooth = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=0,
        adaptive_subdivision=False,
    )
    no_smooth = deformer_no_smooth.deform(mesh, region, vector)
    np.testing.assert_array_almost_equal(
        deformed.vertices, no_smooth.vertices, decimal=12,
    )


def test_taubin_welding_tolerance_scales_with_mesh_size() -> None:
    """Bug #8: ``np.round(decimals=6)`` is fine on meter-scale hulls but
    fails to weld coincident vertices on mm-scale STLs (1 nm tolerance ≪
    float ULP). After the fix, both a 1 m and a 10000 m icosphere must
    produce watertight, non-degenerate output for the same Kracht push,
    proving the welding works at both scales."""
    vector = KrachtVector(
        values={
            "length_ratio":     0.03,
            "breadth_ratio":    0.12,
            "height_ratio":     0.4,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.55,
            "cross_section_c":  0.7,
            "volume_coef":      0.6,
            "nose_sharpness":   0.4,
        }
    )
    deformer = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=3,
        adaptive_subdivision=False,
    )

    small = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    large = trimesh.creation.icosphere(subdivisions=3, radius=10000.0)
    small_region = _bulb_region_from_mesh(small)
    large_region = _bulb_region_from_mesh(large)

    out_small = deformer.deform(small, small_region, vector)
    out_large = deformer.deform(large, large_region, vector)

    assert out_small.is_watertight, "1 m icosphere lost watertightness"
    assert out_large.is_watertight, "10000 m icosphere lost watertightness"

    # Volumes must scale proportionally to (10000/1)**3 — within 5 %.
    ratio = abs(out_large.volume) / abs(out_small.volume)
    expected = 10000.0 ** 3
    drift = abs(ratio - expected) / expected
    assert drift < 0.05, (
        f"Volume ratio {ratio:.3e} drifted {drift*100:.2f}% from expected "
        f"{expected:.3e}: welding likely failed at one of the scales"
    )

    # Neither output should be degenerate (volume not collapsed).
    assert abs(out_small.volume) > 0.5 * abs(small.volume)
    assert abs(out_large.volume) > 0.5 * abs(large.volume)


# ---- B2 Add #2 + Add #5: post-FFD trimesh repair + seam smoothing ---------
#
# Audit C 2026-04-26 (quality strategist):
#
#   Add #2  After ``deformer.deform()`` returns, the mesh is built with
#           ``process=False`` so duplicate vertices and minor non-manifold
#           edges from Taubin / symmetry can persist. The L2 mesh-quality
#           metric ``compute_mesh_quality`` penalises non-watertight meshes
#           with WATERTIGHT_PENALTY=100, dominating any genuine quality
#           signal and steering NSGA-II away from candidates that just need
#           a ``merge_vertices`` pass. Fix: opt-in post-repair with a new
#           ``post_repair`` kwarg defaulting to True.
#
#   Add #5  The smoothstep blend at ``axis_min`` makes the FFD displacement
#           weights C1 continuous, but the *triangulation* across the seam
#           stays unchanged — only positions move. Adjacent triangles
#           inside vs. outside still meet at differing dihedral angles,
#           producing the visible "welding seam" the user complained about.
#           Fix: tiny pure-Laplacian pass on the ring of seam vertices
#           (smoothstep weight in (0.05, 0.95)) controlled by a new
#           ``seam_smoothing_iterations`` kwarg defaulting to 2.


def _vertex_duplicated_hull_for_repair() -> trimesh.Trimesh:
    """Same construction as ``_vertex_duplicated_hull`` but replicated here
    for clarity in B2 Add #2 tests. The 3-verts-per-face layout is the
    canonical "barely-not-watertight" baseline ``merge_vertices`` is
    designed to fix."""
    base = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    base.apply_scale([2.0, 0.75, 0.5])
    new_vertices = base.vertices[base.faces.reshape(-1)]
    new_faces = np.arange(len(new_vertices), dtype=np.int64).reshape(-1, 3)
    duplicated = trimesh.Trimesh(
        vertices=new_vertices,
        faces=new_faces,
        process=False,
    )
    return duplicated


def test_post_repair_yields_watertight_output_after_taubin_disconnections() -> None:
    """B2 Add #2: a coarse hull built from per-face independent vertices
    (the pathological STL layout) is NOT watertight even after FFD +
    welded-Taubin smoothing because trimesh keeps the duplicated vertex
    array intact. Running ``merge_vertices`` + ``process`` after the
    deform pass folds coincident verts back together and re-asserts
    consistent winding, so the output becomes watertight.
    """
    mesh = _vertex_duplicated_hull_for_repair()
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtVector(
        values={
            "length_ratio":     0.03,
            "breadth_ratio":    0.12,
            "height_ratio":     0.4,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.55,
            "cross_section_c":  0.7,
            "volume_coef":      0.6,
            "nose_sharpness":   0.4,
        }
    )

    deformer_repaired = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=3,
        adaptive_subdivision=False,
        post_repair=True,
    )
    deformer_baseline = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=3,
        adaptive_subdivision=False,
        post_repair=False,
    )
    repaired = deformer_repaired.deform(mesh, region, vector)
    baseline = deformer_baseline.deform(mesh, region, vector)

    assert repaired.is_watertight, (
        "post_repair=True should fold coincident verts and yield a "
        "watertight mesh on duplicated-vertex input"
    )
    # Baseline (no repair) is the un-repaired output, which on this
    # pathological mesh is non-watertight. Either way, the two outputs
    # must DIFFER — repair changes vertex count from 3*F to V_unique.
    assert len(repaired.vertices) != len(baseline.vertices), (
        "post_repair=True should change topology vs post_repair=False on "
        "duplicated-vertex input"
    )


def test_seam_smoothing_reduces_dihedral_jump_across_blend_boundary() -> None:
    """B2 Add #5: the smoothstep blend at ``axis_min`` is C1 in
    *displacement weight* but the triangulation across the seam stays
    unchanged — adjacent triangles inside vs. outside the bulb meet at
    measurably different dihedral angles (the "welding seam"). A tiny
    Laplacian pass on the ring of seam vertices levels the dihedral
    without disturbing the rest of the hull.

    Metric: maximum angle between adjacent face normals for faces with
    at least one vertex whose smoothstep weight lies in (0.05, 0.95).
    With ``seam_smoothing_iterations=2`` this should be at least 5 %
    smaller than with ``seam_smoothing_iterations=0``.
    """
    mesh = trimesh.creation.icosphere(subdivisions=4, radius=1.0)
    mesh.apply_scale([2.0, 0.75, 0.5])
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtVector(
        values={
            "length_ratio":     0.04,
            "breadth_ratio":    0.15,
            "height_ratio":     0.5,
            "axis_z_ratio":     0.3,
            "longitudinal_pos": 0.7,
            "cross_section_c":  0.8,
            "volume_coef":      0.7,
            "nose_sharpness":   0.3,
        }
    )

    def _max_dihedral_in_seam_ring(deformed: trimesh.Trimesh, region: dict) -> float:
        """Max angle (radians) between adjacent face normals for any pair
        of faces sharing an edge where at least one face touches the seam
        ring (smoothstep weight ∈ (0.05, 0.95))."""
        primary = int(region["axis_index"])
        ax_min = float(region["axis_min"])
        ax_max = float(region["axis_max"])
        blend_width = 0.10 * (ax_max - ax_min)
        blend_start = ax_min - blend_width
        v = np.asarray(deformed.vertices, dtype=float)
        axis_vals = v[:, primary]
        if blend_width > 0:
            raw = (axis_vals - blend_start) / blend_width
        else:
            raw = np.where(axis_vals >= ax_min, 1.0, 0.0)
        t = np.clip(raw, 0.0, 1.0)
        weights = t * t * (3.0 - 2.0 * t)
        ring_mask = (weights > 0.05) & (weights < 0.95)
        ring_indices = set(np.nonzero(ring_mask)[0].tolist())

        faces = np.asarray(deformed.faces, dtype=np.int64)
        # Mark faces that touch the ring.
        touches_ring = np.array(
            [any(int(idx) in ring_indices for idx in face) for face in faces],
            dtype=bool,
        )
        if not touches_ring.any():
            return 0.0

        # Face normals.
        tri = v[faces]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n_norm = np.linalg.norm(n, axis=1, keepdims=True)
        n_norm = np.where(n_norm > 0, n_norm, 1.0)
        n = n / n_norm

        # Build edge -> face map.
        from collections import defaultdict
        edges_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
        for fi, face in enumerate(faces):
            a, b, c = int(face[0]), int(face[1]), int(face[2])
            for e in ((a, b), (b, c), (c, a)):
                key = (min(e), max(e))
                edges_to_faces[key].append(fi)

        max_angle = 0.0
        for fids in edges_to_faces.values():
            if len(fids) != 2:
                continue
            f1, f2 = fids
            if not (touches_ring[f1] or touches_ring[f2]):
                continue
            cos_t = float(np.clip(np.dot(n[f1], n[f2]), -1.0, 1.0))
            angle = float(np.arccos(cos_t))
            if angle > max_angle:
                max_angle = angle
        return max_angle

    deformer_no_seam = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=3,
        adaptive_subdivision=False,
        post_repair=False,
        seam_smoothing_iterations=0,
    )
    deformer_with_seam = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=3,
        adaptive_subdivision=False,
        post_repair=False,
        seam_smoothing_iterations=2,
    )
    no_seam = deformer_no_seam.deform(mesh, region, vector)
    with_seam = deformer_with_seam.deform(mesh, region, vector)

    dihedral_no = _max_dihedral_in_seam_ring(no_seam, region)
    dihedral_yes = _max_dihedral_in_seam_ring(with_seam, region)

    assert dihedral_no > 0.0, "Test setup did not exercise the seam ring"
    assert dihedral_yes < dihedral_no * 0.95, (
        f"Seam smoothing did not flatten dihedral enough: "
        f"no_seam={np.degrees(dihedral_no):.2f}deg, "
        f"with_seam={np.degrees(dihedral_yes):.2f}deg "
        f"(want ≥5% reduction)"
    )


def test_post_repair_can_be_disabled_for_topology_invariant_tests() -> None:
    """B2 Add #2: with ``post_repair=False, adaptive_subdivision=False``
    the output must keep EXACTLY the input vertex count so legacy tests
    relying on bit-identical vertex-array invariance (``test_deformer_
    preserves_face_topology``, ``test_deformer_freezes_vertices_outside_
    bulb_region``) keep passing without modification."""
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    mesh.apply_scale([2.0, 0.75, 0.5])
    region = _bulb_region_from_mesh(mesh)
    vector = KrachtVector(
        values={
            "length_ratio":     0.03,
            "breadth_ratio":    0.12,
            "height_ratio":     0.4,
            "axis_z_ratio":     0.25,
            "longitudinal_pos": 0.55,
            "cross_section_c":  0.7,
            "volume_coef":      0.6,
            "nose_sharpness":   0.4,
        }
    )

    deformer_no_repair = BulbFFDDeformer(
        force_port_starboard_symmetry=False,
        post_smoothing_iterations=0,
        adaptive_subdivision=False,
        post_repair=False,
    )
    out_no_repair = deformer_no_repair.deform(mesh, region, vector)
    assert len(out_no_repair.vertices) == len(mesh.vertices), (
        "post_repair=False must preserve exact vertex count for the "
        "bit-identical-vertex-array invariant"
    )
