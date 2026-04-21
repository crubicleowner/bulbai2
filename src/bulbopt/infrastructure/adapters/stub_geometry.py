from __future__ import annotations

from pathlib import Path

import numpy as np
import pymeshfix
import trimesh

from bulbopt.storage.filesystem.json_store import JsonStore


class StubGeometryAdapter:
    def __init__(self, json_store: JsonStore | None = None) -> None:
        self._json_store = json_store or JsonStore()

    def prepare_geometry(self, case_dir: Path, source_path: Path) -> dict:
        source_bytes = source_path.read_bytes()
        input_copy_path = case_dir / "input" / source_path.name
        input_copy_path.write_bytes(source_bytes)

        source_mesh = self._load_mesh(source_path)
        before_stats = {
            "vertices_count_before": int(len(source_mesh.vertices)),
            "faces_count_before": int(len(source_mesh.faces)),
            "watertight_before": bool(source_mesh.is_watertight),
        }

        repaired_path = case_dir / "working" / "repaired" / "repaired.stl"
        if before_stats["watertight_before"]:
            repaired_path.write_bytes(source_bytes)
            repaired_mesh = source_mesh
            repaired = False
            repair_status = "not_needed"
        else:
            try:
                repaired_mesh = self._repair_with_pymeshfix(source_mesh)
            except ValueError:
                repaired_path.write_bytes(source_bytes)
                repaired_mesh = source_mesh
                repaired = False
                repair_status = "failed"
            else:
                repaired_path.write_bytes(trimesh.exchange.stl.export_stl(repaired_mesh))
                repaired = True
                repair_status = "repaired"

        analysis = self._build_geometry_analysis(
            repaired_mesh,
            repaired_path,
            before_stats=before_stats,
            repaired=repaired,
            repair_status=repair_status,
        )
        self._json_store.write(case_dir / "working" / "repaired" / "geometry_analysis.json", analysis)
        self._update_artifacts_index(
            case_dir,
            {
                "source_stl": str(input_copy_path),
                "repaired_stl": str(repaired_path),
                "geometry_analysis": str(case_dir / "working" / "repaired" / "geometry_analysis.json"),
            },
        )
        return analysis

    def _repair_with_pymeshfix(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        fix = pymeshfix.MeshFix(np.asarray(mesh.vertices, dtype=float), np.asarray(mesh.faces, dtype=np.int64))
        fix.repair()
        repaired_mesh = trimesh.Trimesh(vertices=fix.points, faces=fix.faces, process=True)
        if repaired_mesh.is_empty:
            raise ValueError("PyMeshFix repair produced an empty mesh")
        return repaired_mesh

    def generate_candidates(
        self,
        case_dir: Path,
        count: int,
        optimization_mode: str = "generate_new_bulb",
    ) -> list[dict]:
        repaired_path = case_dir / "working" / "repaired" / "repaired.stl"
        analysis_path = case_dir / "working" / "repaired" / "geometry_analysis.json"
        mesh = self._load_mesh(repaired_path)
        analysis = self._json_store.read(analysis_path)

        candidates: list[dict] = []
        candidate_paths: dict[str, str] = {}
        for index, profile in enumerate(self._candidate_profiles(count, optimization_mode), start=1):
            candidate_id = f"candidate-{index}"
            candidate_path = case_dir / "working" / "candidates" / f"{candidate_id}.stl"
            candidate_mesh = self._deform_bow_region(mesh, analysis, profile)
            candidate_path.write_bytes(trimesh.exchange.stl.export_stl(candidate_mesh))
            candidate_paths[candidate_id] = str(candidate_path)
            profile_with_mode = {**profile, "optimization_mode": optimization_mode}
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "geometry_path": str(candidate_path),
                    "status": "generated",
                    "generation_profile": profile_with_mode,
                    "bulb_region": analysis["bulb_region"],
                }
            )
        self._update_artifacts_index(case_dir, {"candidates": candidate_paths})
        return candidates

    def _load_mesh(self, source_path: Path) -> trimesh.Trimesh:
        mesh = trimesh.load(source_path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty:
            raise ValueError(f"Unable to load STL mesh: {source_path}")
        if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
            raise ValueError(f"STL mesh is empty: {source_path}")
        mesh = mesh.copy()
        mesh.remove_unreferenced_vertices()
        return mesh

    def _build_geometry_analysis(
        self,
        mesh: trimesh.Trimesh,
        repaired_path: Path,
        *,
        before_stats: dict[str, int | bool] | None = None,
        repaired: bool = False,
        repair_status: str = "not_needed",
    ) -> dict:
        bounds = mesh.bounds.astype(float)
        extents = mesh.extents.astype(float)
        primary_axis = int(np.argmax(extents))
        axis_values = mesh.vertices[:, primary_axis]
        axis_min = float(axis_values.min())
        axis_max = float(axis_values.max())
        region_depth = max(float(extents[primary_axis]) * 0.15, 1e-6)
        bulb_region_min = axis_max - region_depth
        mask_ratio = float(np.mean(axis_values >= bulb_region_min))

        volume = 0.0
        if mesh.is_volume:
            volume = float(abs(mesh.volume))

        before_stats = before_stats or {
            "vertices_count_before": int(len(mesh.vertices)),
            "faces_count_before": int(len(mesh.faces)),
            "watertight_before": bool(mesh.is_watertight),
        }

        return {
            "quality_report": {
                "watertight": bool(mesh.is_watertight),
                "repaired": bool(repaired),
                "repair_status": str(repair_status),
                "vertices_count": int(len(mesh.vertices)),
                "faces_count": int(len(mesh.faces)),
                "vertices_count_before": int(before_stats["vertices_count_before"]),
                "faces_count_before": int(before_stats["faces_count_before"]),
                "watertight_before": bool(before_stats["watertight_before"]),
                "surface_area": float(mesh.area),
                "volume": volume,
                "bounds": bounds.tolist(),
                "extents": extents.tolist(),
                "primary_axis": primary_axis,
            },
            "repaired_path": str(repaired_path),
            "bulb_region": {
                "axis_index": primary_axis,
                "axis_min": bulb_region_min,
                "axis_max": axis_max,
                "mask_ratio": mask_ratio,
            },
        }

    def _candidate_profiles(
        self,
        count: int,
        optimization_mode: str = "generate_new_bulb",
    ) -> list[dict[str, float]]:
        """Per spec §11.3/§11.4 the two modes produce different deformation sets.

        ``generate_new_bulb`` pushes the bow aggressively to create distinctly
        different bulb candidates; ``local_optimize`` keeps amplitudes small
        so the user gets local refinement of an already-existing bulb.
        """
        if optimization_mode == "local_optimize":
            base_profiles = [
                {"axial_push": 0.003, "beam_scale": 0.004, "draft_scale": -0.002},
                {"axial_push": 0.005, "beam_scale": 0.006, "draft_scale": -0.003},
                {"axial_push": 0.007, "beam_scale": 0.008, "draft_scale": -0.004},
            ]
            growth_step = (0.0015, 0.002, -0.001)
        else:
            base_profiles = [
                {"axial_push": 0.008, "beam_scale": 0.012, "draft_scale": -0.006},
                {"axial_push": 0.014, "beam_scale": 0.02, "draft_scale": -0.01},
                {"axial_push": 0.02, "beam_scale": 0.028, "draft_scale": -0.014},
            ]
            growth_step = (0.003, 0.004, -0.002)

        if count <= len(base_profiles):
            return base_profiles[:count]

        profiles = list(base_profiles)
        last_profile = base_profiles[-1]
        while len(profiles) < count:
            scale = len(profiles) - len(base_profiles) + 1
            profiles.append(
                {
                    "axial_push": last_profile["axial_push"] + (growth_step[0] * scale),
                    "beam_scale": last_profile["beam_scale"] + (growth_step[1] * scale),
                    "draft_scale": last_profile["draft_scale"] + (growth_step[2] * scale),
                }
            )
        return profiles

    def _deform_bow_region(
        self,
        mesh: trimesh.Trimesh,
        analysis: dict,
        profile: dict[str, float],
    ) -> trimesh.Trimesh:
        candidate_mesh = mesh.copy()
        vertices = candidate_mesh.vertices.copy()
        bulb_region = analysis["bulb_region"]
        primary_axis = int(bulb_region["axis_index"])
        axis_min = float(bulb_region["axis_min"])
        axis_max = float(bulb_region["axis_max"])
        axis_span = max(axis_max - axis_min, 1e-6)

        axis_values = vertices[:, primary_axis]
        weights = np.clip((axis_values - axis_min) / axis_span, 0.0, 1.0) ** 2
        bounds_center = candidate_mesh.bounds.mean(axis=0)
        extents = candidate_mesh.extents.astype(float)

        vertices[:, primary_axis] += weights * extents[primary_axis] * float(profile["axial_push"])

        secondary_axes = [axis for axis in range(3) if axis != primary_axis]
        for offset_index, axis in enumerate(secondary_axes):
            base_factor = float(profile["beam_scale"] if offset_index == 0 else profile["draft_scale"])
            centered = vertices[:, axis] - bounds_center[axis]
            vertices[:, axis] = bounds_center[axis] + centered * (1.0 + (weights * base_factor))

        candidate_mesh.vertices = vertices
        candidate_mesh.remove_unreferenced_vertices()
        return candidate_mesh

    def _update_artifacts_index(self, case_dir: Path, payload: dict) -> None:
        artifacts_path = case_dir / "artifacts_index.json"
        current_payload = self._json_store.read(artifacts_path)
        current_payload.update(payload)
        self._json_store.write(artifacts_path, current_payload)
