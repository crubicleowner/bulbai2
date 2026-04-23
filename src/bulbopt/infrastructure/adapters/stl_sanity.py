"""STL sanity validator — companion check alongside every top-candidate
STL written to ``outputs/top_candidates/candidate-XXX/``.

Design reference: 2026-04-23-bulbopt-mesh-quality-design.md §4 (L6).

``validate_stl(mesh) -> dict`` returns six fields:

    watertight          bool
    winding_consistent  bool
    volume              float    (zero for broken/flat meshes)
    vertex_count        int
    face_count          int
    checks_passed       bool     (True iff all the other invariants hold)

The use case writes this dict as ``stl_valid.json`` next to each STL,
and the night-run HTML report consumes the failure list to surface a
warning block.
"""
from __future__ import annotations

from typing import Any, Dict

import trimesh


def validate_stl(mesh: trimesh.Trimesh) -> Dict[str, Any]:
    """Inspect a Trimesh and return the sanity-check summary.

    All numerical fields are plain Python floats / ints so the result
    can be JSON-serialised without ``default=str`` hacks.
    """
    try:
        watertight = bool(mesh.is_watertight)
    except Exception:
        watertight = False

    try:
        winding_consistent = bool(mesh.is_winding_consistent)
    except Exception:
        winding_consistent = False

    try:
        if mesh.is_volume:
            volume = float(abs(mesh.volume))
        else:
            volume = 0.0
    except Exception:
        volume = 0.0

    vertex_count = int(len(mesh.vertices))
    face_count = int(len(mesh.faces))

    checks_passed = bool(
        watertight
        and winding_consistent
        and volume > 0.0
        and vertex_count > 0
        and face_count > 0
    )

    return {
        "watertight": watertight,
        "winding_consistent": winding_consistent,
        "volume": volume,
        "vertex_count": vertex_count,
        "face_count": face_count,
        "checks_passed": checks_passed,
    }
