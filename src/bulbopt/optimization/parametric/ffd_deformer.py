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

        out = trimesh.Trimesh(
            vertices=deformed_vertices,
            faces=mesh.faces,
            process=False,
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
