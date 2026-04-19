from __future__ import annotations

from pathlib import Path

import trimesh


class StubEvaluationAdapter:
    def evaluate_candidates(self, candidates: list[dict]) -> list[dict]:
        evaluated: list[dict] = []
        for candidate in candidates:
            candidate_path = Path(candidate["geometry_path"])
            repaired_path = candidate_path.parents[1] / "repaired" / "repaired.stl"
            candidate_mesh = self._load_mesh(candidate_path)
            repaired_mesh = self._load_mesh(repaired_path)
            geometry_metrics = self._build_geometry_metrics(candidate, candidate_mesh, repaired_mesh)
            score_components = self._build_score_components(geometry_metrics)
            resistance_proxy = max(score_components["resistance_proxy"], 1e-6)
            fast_score = round(1.0 / resistance_proxy, 6)
            mid_score = round(
                resistance_proxy
                - (0.8 * geometry_metrics["axial_gain_m"])
                - (0.1 * geometry_metrics["draft_reduction_m"])
                + (0.05 * geometry_metrics["beam_growth_m"]),
                6,
            )
            evaluated.append(
                {
                    **candidate,
                    "status": "mid_score_ready",
                    "fast_score": fast_score,
                    "mid_score": mid_score,
                    "geometry_metrics": geometry_metrics,
                    "score_components": score_components,
                }
            )
        return evaluated

    def _load_mesh(self, source_path: Path) -> trimesh.Trimesh:
        mesh = trimesh.load(source_path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty:
            raise ValueError(f"Unable to load mesh for evaluation: {source_path}")
        mesh = mesh.copy()
        mesh.remove_unreferenced_vertices()
        return mesh

    def _build_geometry_metrics(
        self,
        candidate: dict,
        candidate_mesh: trimesh.Trimesh,
        repaired_mesh: trimesh.Trimesh,
    ) -> dict[str, float]:
        bulb_region = candidate.get("bulb_region", {})
        primary_axis = int(bulb_region.get("axis_index", int(candidate_mesh.extents.argmax())))
        beam_axis, draft_axis = [axis for axis in range(3) if axis != primary_axis]

        candidate_extents = candidate_mesh.extents.astype(float)
        repaired_extents = repaired_mesh.extents.astype(float)

        vertices = candidate_mesh.vertices
        nose_threshold = float(bulb_region.get("axis_min", float(vertices[:, primary_axis].min())))
        nose_mask = vertices[:, primary_axis] >= nose_threshold
        if nose_mask.any():
            nose_vertices = vertices[nose_mask]
            nose_area_proxy = float(
                (nose_vertices[:, beam_axis].max() - nose_vertices[:, beam_axis].min())
                * (nose_vertices[:, draft_axis].max() - nose_vertices[:, draft_axis].min())
            )
        else:
            nose_area_proxy = float(candidate_extents[beam_axis] * candidate_extents[draft_axis])

        beam_extent = float(candidate_extents[beam_axis])
        draft_extent = float(candidate_extents[draft_axis])
        axial_extent = float(candidate_extents[primary_axis])
        repaired_beam = float(repaired_extents[beam_axis])
        repaired_draft = float(repaired_extents[draft_axis])
        repaired_axial = float(repaired_extents[primary_axis])

        return {
            "axial_extent_m": axial_extent,
            "beam_extent_m": beam_extent,
            "draft_extent_m": draft_extent,
            "surface_area_m2": float(candidate_mesh.area),
            "slenderness_ratio": axial_extent / max(beam_extent, draft_extent, 1e-6),
            "nose_area_proxy_m2": nose_area_proxy,
            "axial_gain_m": max(axial_extent - repaired_axial, 0.0),
            "beam_growth_m": max(beam_extent - repaired_beam, 0.0),
            "draft_reduction_m": max(repaired_draft - draft_extent, 0.0),
        }

    def _build_score_components(self, geometry_metrics: dict[str, float]) -> dict[str, float]:
        frontal_area_proxy = geometry_metrics["beam_extent_m"] * geometry_metrics["draft_extent_m"]
        resistance_proxy = frontal_area_proxy / max(geometry_metrics["axial_extent_m"], 1e-6)
        return {
            "frontal_area_proxy_m2": round(frontal_area_proxy, 6),
            "resistance_proxy": max(round(resistance_proxy, 6), 1e-6),
        }
