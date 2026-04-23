"""Free-Form Deformation of the bulb region.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §4.2.

We implement tri-variate Bezier (Bernstein-basis) FFD directly on numpy
because the canonical SISSA PyGeM is not on PyPI and installing it via git
is fragile inside a laptop environment. The math is short and well-tested:

  P_new(s,t,u) = P_old + sum_{i=0..l, j=0..m, k=0..n}
                       B_i^l(s) * B_j^m(t) * B_k^n(u) * dP_ijk

where B_i^l is the ith Bernstein polynomial of degree l and s,t,u are the
point's normalised coordinates inside the control box. Offsets dP_ijk at
the control lattice corners deform the volume, and the deformation smoothly
vanishes at the box boundaries — exactly what we want for a local bulb
region edit.

The deformer is intentionally decoupled from the Kracht space: ``deform``
takes an already-sampled ``KrachtVector`` and maps its 8 parameters onto
lattice offsets. That mapping is deterministic, lives in one place
(``_kracht_to_lattice_offsets``), and is the only knob to tune if the
generated bulbs look wrong.
"""
from __future__ import annotations

from math import comb
from typing import Tuple

import numpy as np
import trimesh

from bulbopt.optimization.parametric.kracht_space import KrachtVector


class BulbFFDDeformer:
    """Deform a mesh's bulb region via a tri-variate Bezier FFD lattice."""

    LATTICE_SHAPE: Tuple[int, int, int] = (5, 4, 4)
    # Degree of the Bernstein basis per axis is n_cp - 1.

    # Smooth blend before axis_min so the deformed bulb joins the rest of the
    # hull with C1 continuity (spec 2026-04-23 §3 Fix A). Width is a fraction
    # of the bulb length (axis_max - axis_min).
    BLEND_WIDTH_FRACTION: float = 0.10

    def __init__(
        self,
        force_port_starboard_symmetry: bool = True,
        post_smoothing_iterations: int = 3,
        adaptive_subdivision: bool = True,
        adaptive_min_triangles: int = 500,
        adaptive_max_iterations: int = 3,
    ) -> None:
        """
        Parameters
        ----------
        force_port_starboard_symmetry:
            When True (default), the deformer enforces mirror symmetry of
            the output mesh around the beam midplane (spec 2026-04-23 §3
            Fix B). This is defensive: even if the baseline STL has tiny
            triangulation asymmetries, the engineer still gets a
            mirror-clean bulb.
        post_smoothing_iterations:
            Number of Taubin smoothing passes applied after FFD. Taubin
            alternates a positive Laplacian step (smoothing) with a
            negative one (anti-smoothing) so the low-frequency shape is
            preserved (volume drift ≤ 1% after 3 iterations) while the
            polygonal facet edges are rounded (spec 2026-04-23 §3 Fix C).
            Set to 0 to disable smoothing (useful for volume tests).
        adaptive_subdivision:
            Opt-in triangle densification before FFD (spec 2026-04-23 §4
            L5). When True, the bulb region is subdivided up to
            ``adaptive_max_iterations`` times until it contains at least
            ``adaptive_min_triangles`` triangles, so FFD has enough
            resolution to avoid polygonal facets in the output.
        adaptive_min_triangles:
            Triangle count threshold for the region. Default 500.
        adaptive_max_iterations:
            Hard cap on subdivision passes (prevents runaway on coarse
            baselines). Default 3.
        """
        self.force_port_starboard_symmetry = bool(force_port_starboard_symmetry)
        self.post_smoothing_iterations = max(int(post_smoothing_iterations), 0)
        self.adaptive_subdivision = bool(adaptive_subdivision)
        self.adaptive_min_triangles = max(int(adaptive_min_triangles), 1)
        self.adaptive_max_iterations = max(int(adaptive_max_iterations), 0)

    def deform(
        self,
        mesh: trimesh.Trimesh,
        region: dict,
        vector: KrachtVector,
    ) -> trimesh.Trimesh:
        """Return a copy of ``mesh`` with bulb-region vertices displaced.

        Vertices outside ``region`` are bit-identical to the input.
        Topology (faces, order) is unchanged so a watertight input stays
        watertight on output.
        """
        primary_axis = int(region["axis_index"])
        axis_min = float(region["axis_min"])
        axis_max = float(region["axis_max"])
        if axis_max <= axis_min:
            return mesh.copy()

        # Spec 2026-04-23 §4 L5: densify the bulb region before FFD so we
        # always have at least ``adaptive_min_triangles`` tris in the
        # deformation zone. This is a no-op when the input already meets
        # the threshold or the hook is disabled at __init__.
        if self.adaptive_subdivision:
            # Local import keeps the ffd_deformer module importable in
            # environments where adaptive_subdivision has missing deps.
            from bulbopt.optimization.parametric.adaptive_subdivision import (
                subdivide_region,
            )

            mesh = subdivide_region(
                mesh,
                region,
                min_triangles=self.adaptive_min_triangles,
                max_iterations=self.adaptive_max_iterations,
            )

        # Spec 2026-04-23 §3 Fix A: smooth blend across the boundary. The
        # participating region extends BLEND_WIDTH_FRACTION × (axis_max -
        # axis_min) aft of axis_min; every vertex there gets a smoothstep
        # weight from 0 (at blend_start) to 1 (at axis_min), so there is
        # no C0 discontinuity across the boundary.
        blend_width = self.BLEND_WIDTH_FRACTION * (axis_max - axis_min)
        blend_start = axis_min - blend_width

        participating = mesh.vertices[:, primary_axis] >= blend_start
        if not np.any(participating):
            return mesh.copy()

        deformed_vertices = mesh.vertices.copy()

        # Build control box in the bulb region's bounding volume so the
        # deformation tapers to zero on the aft-most side (where the hull
        # glues back into the rest of the mesh).
        region_vertices = mesh.vertices[participating]
        box_origin, box_size = self._region_box(
            region_vertices,
            primary_axis=primary_axis,
            axis_min=axis_min,
            axis_max=axis_max,
        )

        offsets = self._kracht_to_lattice_offsets(
            vector=vector,
            primary_axis=primary_axis,
            box_size=box_size,
        )

        deformed_region = self._apply_ffd(
            points=region_vertices,
            box_origin=box_origin,
            box_size=box_size,
            offsets=offsets,
        )

        # Blend weights: 0 at blend_start, 1 at axis_min, 1 beyond.
        axis_values = region_vertices[:, primary_axis]
        if blend_width > 0:
            raw = (axis_values - blend_start) / blend_width
        else:
            raw = np.where(axis_values >= axis_min, 1.0, 0.0)
        t = np.clip(raw, 0.0, 1.0)
        # smoothstep (Hermite) for C1 continuity at both ends.
        weights = t * t * (3.0 - 2.0 * t)
        # Apply weighted displacement back to the original vertices.
        weighted_displacement = (deformed_region - region_vertices) * weights[:, None]
        deformed_vertices[participating] = region_vertices + weighted_displacement

        if self.force_port_starboard_symmetry:
            other_axes = [a for a in range(3) if a != primary_axis]
            beam_axis = other_axes[0]
            # Only symmetrize vertices that actually participate in the
            # deformation — leave the rest of the hull alone so legacy
            # topology is preserved bit-identical.
            participating_indices = np.nonzero(participating)[0]
            deformed_vertices = _enforce_mirror_symmetry_subset(
                vertices=deformed_vertices,
                beam_axis=beam_axis,
                subset_indices=participating_indices,
                primary_axis=primary_axis,
            )

        out = trimesh.Trimesh(
            vertices=deformed_vertices,
            faces=mesh.faces,
            process=False,
        )

        # Spec 2026-04-23 §3 Fix C: Taubin volume-preserving smoothing.
        # Lambda=0.5, Nu=-0.53 is the classic pair from Taubin 1995 that
        # preserves low-frequency shape while rounding high-frequency
        # facet edges. We apply this only to bulb-region vertices so the
        # rest of the hull keeps its original triangulation.
        if self.post_smoothing_iterations > 0:
            _apply_taubin_to_region(
                out,
                primary_axis=primary_axis,
                blend_start=blend_start,
                blend_width=blend_width,
                iterations=self.post_smoothing_iterations,
            )
            # Re-assert symmetry after smoothing (Laplacian can drift
            # micro-asymmetries back in). Keep the same subset scope.
            if self.force_port_starboard_symmetry:
                beam_axis = [a for a in range(3) if a != primary_axis][0]
                out.vertices = _enforce_mirror_symmetry_subset(
                    vertices=np.asarray(out.vertices),
                    beam_axis=beam_axis,
                    subset_indices=np.nonzero(participating)[0],
                    primary_axis=primary_axis,
                )

        return out

    # ---- geometry helpers -------------------------------------------------

    def _region_box(
        self,
        vertices: np.ndarray,
        *,
        primary_axis: int,
        axis_min: float,
        axis_max: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Axis-aligned bounding box enclosing the bulb region."""
        other_axes = [axis for axis in range(3) if axis != primary_axis]
        origin = np.zeros(3, dtype=float)
        size = np.zeros(3, dtype=float)
        origin[primary_axis] = axis_min
        size[primary_axis] = max(axis_max - axis_min, 1e-9)
        for axis in other_axes:
            lo = float(vertices[:, axis].min())
            hi = float(vertices[:, axis].max())
            # Pad laterally so boundary vertices sit strictly inside the
            # box and their weights are well-defined at the edges.
            pad = max((hi - lo) * 0.05, 1e-6)
            origin[axis] = lo - pad
            size[axis] = (hi - lo) + 2.0 * pad
        return origin, size

    # ---- Kracht → lattice offsets ----------------------------------------

    def _kracht_to_lattice_offsets(
        self,
        *,
        vector: KrachtVector,
        primary_axis: int,
        box_size: np.ndarray,
    ) -> np.ndarray:
        """Map an 8-D Kracht sample onto (l, m, n, 3) lattice offsets.

        The mapping is deterministic and smooth: each Kracht parameter
        contributes to one or two lattice dimensions, and the overall
        magnitude is scaled by the physical ``box_size`` so the deformation
        feels consistent across hulls of different scale.
        """
        l_cp, m_cp, n_cp = self.LATTICE_SHAPE
        offsets = np.zeros((l_cp, m_cp, n_cp, 3), dtype=float)

        v = vector.values
        axis_primary = primary_axis
        axes_secondary = [a for a in range(3) if a != primary_axis]
        beam_axis = axes_secondary[0]
        draft_axis = axes_secondary[1]

        # Length: push the forward-most lattice slab along the primary axis
        # by length_ratio * box_length.
        length_push = v["length_ratio"] * box_size[axis_primary]
        longitudinal_weight = v["longitudinal_pos"]
        for i in range(l_cp):
            # quadratic weight biased by longitudinal_pos toward nose
            frac = i / max(l_cp - 1, 1)
            weight = (frac ** 2) * (0.5 + 0.5 * longitudinal_weight)
            offsets[i, :, :, axis_primary] += weight * length_push

        # Breadth: expand middle-height lattice slabs outward in beam
        # direction by +/- breadth_ratio * B.
        breadth_push = v["breadth_ratio"] * box_size[beam_axis] * 0.5
        for i in range(l_cp):
            frac_i = i / max(l_cp - 1, 1)
            length_weight = (frac_i ** 1.5)
            for j in range(m_cp):
                centred = (j / max(m_cp - 1, 1)) - 0.5
                # positive on +beam side, negative on -beam side
                sign = 1.0 if centred > 0 else (-1.0 if centred < 0 else 0.0)
                # stronger in the middle of the length
                offsets[i, j, :, beam_axis] += sign * length_weight * breadth_push

        # Height: stretch lattice vertically by height_ratio * T, biased by
        # axis_z_ratio (axis offset from baseline).
        height_push = v["height_ratio"] * box_size[draft_axis] * 0.5
        axis_z = (v["axis_z_ratio"] - 0.25) * box_size[draft_axis]
        for i in range(l_cp):
            frac_i = i / max(l_cp - 1, 1)
            length_weight = (frac_i ** 1.5)
            for k in range(n_cp):
                centred = (k / max(n_cp - 1, 1)) - 0.5
                sign = 1.0 if centred > 0 else (-1.0 if centred < 0 else 0.0)
                offsets[i, :, k, draft_axis] += sign * length_weight * height_push
            # axis shift (whole slab translates vertically)
            offsets[i, :, :, draft_axis] += length_weight * axis_z

        # Cross-section shape: pull corners toward circular (c=1) or keep
        # ellipse (c=0.25) by blending diagonal lattice points.
        c = v["cross_section_c"]
        circle_pull = (c - 0.5) * 0.15 * max(box_size[beam_axis], box_size[draft_axis])
        for i in range(l_cp):
            for j in (0, m_cp - 1):
                for k in (0, n_cp - 1):
                    # push diagonal corners toward axis centre
                    centre_dir_beam = -1.0 if j == 0 else 1.0
                    centre_dir_draft = -1.0 if k == 0 else 1.0
                    offsets[i, j, k, beam_axis] -= centre_dir_beam * circle_pull
                    offsets[i, j, k, draft_axis] -= centre_dir_draft * circle_pull

        # Volume coefficient: overall magnitude scale (0.4 -> 0.9 multiplier).
        offsets *= 0.5 + v["volume_coef"]

        # Nose sharpness: taper the forward-most slab inward so sharp (0)
        # gives a pointy nose, rounded (1) leaves dome intact.
        sharpness = v["nose_sharpness"]
        taper = (1.0 - sharpness) * 0.3
        for j in (0, m_cp - 1):
            for k in (0, n_cp - 1):
                offsets[l_cp - 1, j, k, beam_axis] -= (
                    (1.0 if j == m_cp - 1 else -1.0) * taper * box_size[beam_axis] * 0.1
                )
                offsets[l_cp - 1, j, k, draft_axis] -= (
                    (1.0 if k == n_cp - 1 else -1.0) * taper * box_size[draft_axis] * 0.1
                )

        # F5 (mesh-quality design §4): clamp per-lattice-point offset so
        # no single control point moves farther than half the local cell
        # spacing along any axis. This prevents triangle inversion near
        # the nose tip when ``longitudinal_pos`` + low ``nose_sharpness``
        # push two lattice columns past each other — the failure mode
        # Agent 1 saw as 66–76 flipped triangles in the generated mesh.
        spacing = np.zeros(3, dtype=float)
        spacing[axis_primary] = box_size[axis_primary] / max(l_cp - 1, 1)
        spacing[beam_axis] = box_size[beam_axis] / max(m_cp - 1, 1)
        spacing[draft_axis] = box_size[draft_axis] / max(n_cp - 1, 1)
        max_offset = 0.5 * spacing  # 3-vector, broadcasts over (l, m, n)
        # Protect against a degenerate zero-width box direction.
        safe_max = np.where(max_offset > 0, max_offset, 1.0)
        # Clamp symmetrically per axis.
        np.clip(offsets, -safe_max, safe_max, out=offsets)

        return offsets

    # ---- core FFD ---------------------------------------------------------

    def _apply_ffd(
        self,
        *,
        points: np.ndarray,
        box_origin: np.ndarray,
        box_size: np.ndarray,
        offsets: np.ndarray,
    ) -> np.ndarray:
        """Apply the Bernstein-basis FFD sum to ``points``."""
        safe_size = np.where(box_size > 0, box_size, 1.0)
        local = (points - box_origin) / safe_size
        local = np.clip(local, 0.0, 1.0)
        s = local[:, 0]
        t = local[:, 1]
        u = local[:, 2]

        l_cp, m_cp, n_cp = self.LATTICE_SHAPE
        l_deg, m_deg, n_deg = l_cp - 1, m_cp - 1, n_cp - 1

        # Pre-compute per-axis Bernstein tables: shape (n_cp, N).
        bi = np.stack([_bernstein(l_deg, i, s) for i in range(l_cp)], axis=0)
        bj = np.stack([_bernstein(m_deg, j, t) for j in range(m_cp)], axis=0)
        bk = np.stack([_bernstein(n_deg, k, u) for k in range(n_cp)], axis=0)

        # Sum contributions of every lattice point.
        deformed = points.copy()
        for i in range(l_cp):
            for j in range(m_cp):
                for k in range(n_cp):
                    w = (bi[i] * bj[j] * bk[k])[:, None]  # (N, 1)
                    deformed = deformed + w * offsets[i, j, k]
        return deformed


def _bernstein(degree: int, index: int, t: np.ndarray) -> np.ndarray:
    """Compute B_index^degree(t) for an array of parameters t ∈ [0, 1]."""
    coeff = comb(degree, index)
    return coeff * (t ** index) * ((1.0 - t) ** (degree - index))


def _apply_taubin_to_region(
    mesh: trimesh.Trimesh,
    *,
    primary_axis: int,
    blend_start: float,
    blend_width: float,
    iterations: int,
    lamb: float = 0.5,
    nu: float = -0.53,
) -> None:
    """Apply Taubin λ/μ smoothing to vertices that participate in the FFD.

    Done in-place on ``mesh.vertices``. Vertices outside the region
    (axis < blend_start) are explicitly held fixed so the rest of the
    hull triangulation never moves. Inside the blend zone the Taubin
    update is multiplied by a smoothstep weight that rises from 0 at
    ``blend_start`` to 1 at ``blend_start + blend_width`` (mesh-quality
    design §4 Fix F4) — this prevents the C0 discontinuity the original
    binary mask introduced right at the bulb boundary.

    The classic Taubin parameters (λ=0.5, ν=-0.53) satisfy
    λν / (λ+ν) ≈ -0.22 which preserves frequencies below the cutoff —
    low-frequency shape survives, facet edges flatten.

    Critical fix F1 (mesh-quality design §4): build the adjacency graph
    on position-welded vertices rather than raw index-per-face vertices.
    STL loaders typically produce 3 unique vertices per face (no index
    sharing, degree-2 graph), which used to make Taubin collapse the
    mesh by -99% volume. Welding by position (6-decimal quantisation)
    recovers the true surface topology; the welded Laplacian is applied
    per unique position and then scattered back to the original vertex
    array, so the mesh's topology (face indices, vertex count) is
    preserved bit-identical.

    Implementation is fully vectorised: we build a sparse CSR Laplacian
    once (edges derived from faces via numpy, no Python loops) and then
    each smoothing step is one ``A @ positions`` matrix-vector product.
    On a 14 k-vertex hull the previous Python-loop version took ~30 s;
    the vectorised version completes in ~50 ms.
    """
    from scipy.sparse import csr_matrix

    vertices = np.asarray(mesh.vertices, dtype=float)
    n = len(vertices)
    if n == 0 or iterations <= 0:
        return

    # ---- F1: weld coincident vertices by position ------------------------
    #
    # Rounding to 6 decimals matches trimesh.grouping.merge_vertices_hash.
    # ``inverse`` is a length-n array: inverse[k] = the unique-position
    # index that vertices[k] belongs to. Duplicated STL vertices collapse
    # onto a single node in the welded graph so Taubin operates on the
    # proper connected mesh topology.
    rounded = np.round(vertices, decimals=6)
    unique_positions, inverse = np.unique(rounded, axis=0, return_inverse=True)
    n_unique = int(unique_positions.shape[0])

    # Welded face indices: each face's three vertex indices map onto the
    # unique-position space.
    faces = np.asarray(mesh.faces, dtype=np.int64)
    welded_faces = inverse[faces]

    # Edges (undirected) in the welded graph, de-duplicated. Drop self-
    # edges introduced by degenerate faces (all three corners welded onto
    # one node) — they only inflate the diagonal.
    edges = np.concatenate(
        [
            welded_faces[:, [0, 1]],
            welded_faces[:, [1, 2]],
            welded_faces[:, [2, 0]],
        ],
        axis=0,
    )
    edges = edges[edges[:, 0] != edges[:, 1]]
    if len(edges) == 0:
        return
    edges = np.sort(edges, axis=1)
    edges = np.unique(edges, axis=0)

    # Symmetric adjacency on welded graph with 1 / degree_i weights so
    # (A @ positions)[i] = mean(neighbours of i).
    rows = np.concatenate([edges[:, 0], edges[:, 1]])
    cols = np.concatenate([edges[:, 1], edges[:, 0]])
    degree = np.bincount(rows, minlength=n_unique).astype(float)
    safe_degree = np.where(degree > 0, degree, 1.0)
    weights = 1.0 / safe_degree[rows]
    adjacency = csr_matrix((weights, (rows, cols)), shape=(n_unique, n_unique))

    # ---- F4: smoothstep weight on raw vertices instead of binary mask ----
    #
    # ``taper`` is 1 inside the bulb region, 0 outside ``blend_start``, and
    # smoothly 0→1 across the blend zone so the smoothing doesn't clip at
    # the boundary and there is no C0 discontinuity across it.
    raw_axis = vertices[:, primary_axis]
    if blend_width > 0:
        t_raw = (raw_axis - blend_start) / blend_width
    else:
        t_raw = np.where(raw_axis >= blend_start, 1.0, 0.0)
    t_raw = np.clip(t_raw, 0.0, 1.0)
    vertex_taper = t_raw * t_raw * (3.0 - 2.0 * t_raw)

    # Welded-space taper: max over all raw vertices mapped onto each
    # unique position, so a unique node is "movable" if any of its
    # duplicates participate in the deformation.
    welded_taper = np.zeros(n_unique, dtype=float)
    np.maximum.at(welded_taper, inverse, vertex_taper)
    welded_taper_col = welded_taper[:, None]

    original = vertices.copy()

    # Taubin runs on welded positions; compute welded positions as the
    # mean of their duplicates' raw positions.
    welded_positions = np.zeros((n_unique, 3), dtype=float)
    counts = np.bincount(inverse, minlength=n_unique).astype(float)
    safe_counts = np.where(counts > 0, counts, 1.0)
    for dim in range(3):
        welded_positions[:, dim] = (
            np.bincount(inverse, weights=vertices[:, dim], minlength=n_unique)
            / safe_counts
        )

    for _ in range(iterations):
        for step in (lamb, nu):
            neighbour_means = adjacency @ welded_positions
            laplacian = neighbour_means - welded_positions
            welded_positions = welded_positions + step * laplacian * welded_taper_col

    # Scatter welded positions back onto the raw vertex array.
    vertices = welded_positions[inverse]
    # F4: blend the smoothed positions with the originals using the raw
    # taper so the transition at the blend boundary stays continuous
    # (welded_taper is per-unique-node, but duplicates of a mixed node
    # sit at different raw axis coordinates; the raw taper respects
    # that).
    vertices = (
        original * (1.0 - vertex_taper[:, None])
        + vertices * vertex_taper[:, None]
    )

    mesh.vertices = vertices


def _enforce_mirror_symmetry_subset(
    vertices: np.ndarray,
    beam_axis: int,
    subset_indices: np.ndarray,
    primary_axis: int,
) -> np.ndarray:
    """Symmetrise only the vertices in ``subset_indices`` around the beam
    midplane; leave the rest bit-identical.

    Safety guards added after the first naive implementation badly
    collapsed the mesh (volume -29%, surface +199%):

    1. **Subset scope** — only the participating bulb-region vertices get
       touched. The aft cylindrical hull stays exactly where it was.
    2. **Mutual pairing** — a vertex i is only merged with its candidate
       partner j if j's nearest-mirror is also i. Cross-pairings (i→j
       but j→k≠i) are skipped.
    3. **Distance gate** — the mirror distance must be below a local
       threshold derived from the subset's bounding-box diagonal; far
       partners are clearly wrong matches and get skipped.

    Vertices failing the guards keep their pre-symmetry coordinates —
    small residual asymmetry is always preferred over a folded mesh.
    """
    from scipy.spatial import cKDTree

    symmetric = vertices.copy()
    if len(subset_indices) == 0:
        return symmetric

    subset = symmetric[subset_indices]
    mirrors = subset.copy()
    mirrors[:, beam_axis] *= -1.0
    tree = cKDTree(subset)
    # For each subset vertex i, nearest subset vertex to mirror(i).
    distances, partners = tree.query(mirrors, k=1)
    partners = np.asarray(partners, dtype=int)

    # Mutual-pairing mask: partner[partner[i]] == i
    mutual = partners[partners] == np.arange(len(subset))

    # Distance threshold = 2% of subset bounding-box diagonal (small
    # enough to catch cross-pairings, large enough to tolerate mesh
    # noise after FFD displacement).
    bbox_diag = float(np.linalg.norm(subset.max(axis=0) - subset.min(axis=0)))
    threshold = 0.02 * bbox_diag if bbox_diag > 0 else 1e-6

    # F3 (mesh-quality design §4): snapping a self-pair (vertex whose
    # own nearest-mirror is itself) to beam=0 used to collapse any
    # off-centerline vertex without a real mirror partner — e.g. the
    # bottom flange produced 113 vertices with |beam| up to 0.60 m
    # snapped flat to zero, producing the "broken flap" visible in the
    # user's screenshots. Self-pairs are now only collapsed if the
    # vertex is *already* within ``threshold`` of the beam midplane;
    # anything farther out is left at its original position.
    paired: set[int] = set()
    for local_i in range(len(subset)):
        if local_i in paired:
            continue
        local_j = int(partners[local_i])
        if local_i == local_j:
            # Only snap a self-paired vertex to the centerline when it
            # really sits near it already (|beam| < threshold). Farther
            # vertices are leftovers of an asymmetric triangulation and
            # must keep their coordinates.
            if abs(float(subset[local_i][beam_axis])) < threshold:
                global_i = int(subset_indices[local_i])
                symmetric[global_i, beam_axis] = 0.0
            paired.add(local_i)
            continue
        if not mutual[local_i]:
            continue
        if float(distances[local_i]) > threshold:
            continue
        if local_j in paired:
            continue
        global_i = int(subset_indices[local_i])
        global_j = int(subset_indices[local_j])
        avg = 0.5 * (subset[local_i] + mirrors[local_j])
        symmetric[global_i] = avg
        mirrored_avg = avg.copy()
        mirrored_avg[beam_axis] *= -1.0
        symmetric[global_j] = mirrored_avg
        paired.add(local_i)
        paired.add(local_j)

    return symmetric
