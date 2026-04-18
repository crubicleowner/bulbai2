from __future__ import annotations

from pathlib import Path


class StubGeometryAdapter:
    def prepare_geometry(self, case_dir: Path, source_path: Path) -> dict:
        repaired_path = case_dir / "working" / "repaired" / "repaired.stl"
        repaired_path.write_bytes(source_path.read_bytes())
        return {
            "quality_report": {"watertight": False, "repaired": True},
            "repaired_path": str(repaired_path),
            "bulb_region": {"x_min": 0.0, "x_max": 5.0},
        }

    def generate_candidates(self, case_dir: Path, count: int) -> list[dict]:
        candidates: list[dict] = []
        for index in range(count):
            candidate_id = f"candidate-{index + 1}"
            candidate_path = case_dir / "working" / "candidates" / f"{candidate_id}.stl"
            candidate_path.write_text(
                f"solid {candidate_id}\nendsolid {candidate_id}\n",
                encoding="utf-8",
            )
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "geometry_path": str(candidate_path),
                    "status": "generated",
                }
            )
        return candidates
