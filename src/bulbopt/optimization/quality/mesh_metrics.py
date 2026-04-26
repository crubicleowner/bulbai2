"""Mesh-quality scalar metric used as the 3rd NSGA-II objective.

Design reference: 2026-04-23-bulbopt-mesh-quality-design.md §4 (L2).

The GA minimises a composite

    mesh_quality = max(
        dihedral_angle_deviation,   # high-frequency facet roughness
        symmetry_error,             # deviation from y -> -y symmetry
        watertight_penalty,         # 100 if broken, 0 if watertight
    )

so the single worst indicator governs. A broken mesh gets ``>= 100``
which dominates any realistic dihedral/symmetry value, guaranteeing
NSGA-II kills it.

The individual components are intentionally simple so the metric is
cheap enough to run inside the mid-gate on every GA individual.
"""
from __future__ import annotations

import numpy as np
import trimesh


WATERTIGHT_PENALTY = 100.0


def _dihedral_deviation(mesh: trimesh.Trimesh) -> float:
    """RMS deviation of face-adjacency dihedral angles from the local
    mean, normalised into [0, 1].

    A perfectly smooth (curvature-constant) surface has near-zero
    deviation. Facetted or noisy regions have high deviation. We use
    ``mesh.face_adjacency_angles`` which trimesh computes once per mesh.
    """
    try:
        angles = mesh.face_adjacency_angles
    except Exception:
        return 0.0
    if angles is None or len(angles) == 0:
        return 0.0
    a = np.asarray(angles, dtype=float)
    mean = float(np.mean(a))
    deviation = float(np.sqrt(np.mean((a - mean) ** 2)))
    # Scale by pi so an angle spread of a radian maps to ~0.32.
    return deviation / float(np.pi)


def _symmetry_error(
    mesh: trimesh.Trimesh, beam_axis: int | None = None
) -> float:
    """Vertex-to-mirror RMS distance, normalised by bounding-box diagonal.

    Mirrors the hull about its centreline on the beam axis and measures
    how close each vertex is to its mirrored counterpart.

    When ``beam_axis`` is ``None`` (default) the function falls back to
    the legacy ``argmin(extents)`` heuristic — fine for synthetic test
    meshes where all non-primary axes are centered on zero. Production
    callers should pass ``beam_axis=region["beam_axis"]`` so the metric
    measures symmetry around the truly symmetric axis of the hull
    (audit 2026-04-26).

    Returns a non-negative float; 0 means perfectly symmetric.
    """
    vertices = np.asarray(mesh.vertices, dtype=float)
    if vertices.size == 0:
        return 0.0
    extents = mesh.extents.astype(float)
    if np.any(extents <= 0):
        return 0.0

    if beam_axis is None:
        beam_axis = int(np.argmin(extents))
    else:
        beam_axis = int(beam_axis)
    centre = 0.5 * (vertices[:, beam_axis].max() + vertices[:, beam_axis].min())

    mirrored = vertices.copy()
    mirrored[:, beam_axis] = 2.0 * centre - vertices[:, beam_axis]

    # For each mirrored vertex, find the closest original vertex.
    try:
        from scipy.spatial import cKDTree  # type: ignore
    except Exception:
        # Fallback: vectorised pairwise distance (O(N^2)). For typical
        # mid-gate meshes (<= 5k vertices) this is still acceptable.
        diffs = vertices[:, None, :] - mirrored[None, :, :]
        d = np.linalg.norm(diffs, axis=2)
        rms = float(np.sqrt(np.mean(d.min(axis=1) ** 2)))
    else:
        tree = cKDTree(vertices)
        distances, _ = tree.query(mirrored, k=1)
        rms = float(np.sqrt(np.mean(np.asarray(distances, dtype=float) ** 2)))

    diagonal = float(np.linalg.norm(extents))
    if diagonal <= 0:
        return 0.0
    return rms / diagonal


def _watertight_penalty(mesh: trimesh.Trimesh) -> float:
    try:
        if bool(mesh.is_watertight):
            return 0.0
    except Exception:
        pass
    return WATERTIGHT_PENALTY


def compute_mesh_quality(
    deformed: trimesh.Trimesh, beam_axis: int | None = None
) -> float:
    """Return a composite quality scalar for the deformed mesh.

    Lower is better. Non-negative and finite. A broken (non-watertight)
    mesh returns ``>= WATERTIGHT_PENALTY`` so NSGA-II dominates it.

    Pass ``beam_axis`` (typically ``region["beam_axis"]`` from the
    geometry analysis) so the symmetry sub-metric mirrors around the
    truly symmetric axis of the hull. The default ``None`` keeps the
    legacy ``argmin(extents)`` heuristic for callers that don't have a
    beam axis at hand (e.g. unit tests on icospheres / boxes).
    """
    components = (
        _dihedral_deviation(deformed),
        _symmetry_error(deformed, beam_axis=beam_axis),
        _watertight_penalty(deformed),
    )
    return float(max(components))
