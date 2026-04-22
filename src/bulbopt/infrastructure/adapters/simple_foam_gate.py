"""High-fidelity cascade gate that drives the existing OpenFOAM adapter.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §9.

For each KrachtVector the gate:

1. Deforms the baseline mesh via :class:`BulbFFDDeformer`.
2. Writes the deformed STL to a per-candidate working directory.
3. Calls the injected ``build_case`` (normally
   :class:`OpenFOAMAdapter.build_case`) to materialise the OpenFOAM
   case tree around that STL.
4. Calls the injected ``run_case`` (normally
   :class:`OpenFOAMRunnerAdapter.run_case` with ``execute=True``) to
   invoke ``blockMesh`` + ``snappyHexMesh`` (and later ``simpleFoam``
   with ``forceCoeffs``).
5. Returns two objectives per candidate:
     * primary drag proxy (lower is better) — currently a geometric
       surrogate derived from the deformed mesh, upgraded to a real
       ``forceCoeffs`` reading once simpleFoam convergence detection
       lands in ``openfoam_runner``.
     * volume delta relative to baseline (lower is better).

On runner failure the gate returns a penalty fitness rather than
raising, so NSGA-II can still sort the population and the Pareto front
stays interpretable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Sequence
import uuid

import trimesh

from bulbopt.infrastructure.adapters.force_coeffs_parser import (
    ForceCoeffsNotFoundError,
    parse_drag_coefficient_dat,
)
from bulbopt.optimization.parametric.ffd_deformer import BulbFFDDeformer
from bulbopt.optimization.parametric.kracht_space import KrachtVector


BuildCaseFn = Callable[..., dict]
RunCaseFn = Callable[..., dict]


@dataclass(slots=True)
class SimpleFoamHighFidelityGate:
    work_root: Path
    baseline_mesh: trimesh.Trimesh
    region: dict
    deformer: BulbFFDDeformer
    build_case: BuildCaseFn
    run_case: RunCaseFn
    # Reference state for Cd -> Newtons conversion (spec §9). All three
    # must be supplied to enable the conversion; otherwise the gate
    # falls back to the dimensionless coefficient and the proxy delta.
    reference_velocity_m_s: float | None = None
    reference_area_m2: float | None = None
    fluid_density_kg_m3: float | None = None
    _baseline_volume: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self._baseline_volume = _mesh_volume(self.baseline_mesh)
        Path(self.work_root).mkdir(parents=True, exist_ok=True)

    def evaluate(self, vectors: Sequence[KrachtVector]) -> List[List[float]]:
        objectives: List[List[float]] = []
        for vector in vectors:
            row = self._evaluate_one(vector)
            objectives.append(row)
        return objectives

    def _evaluate_one(self, vector: KrachtVector) -> List[float]:
        deformed = self.deformer.deform(self.baseline_mesh, self.region, vector)
        candidate_id = f"candidate-{uuid.uuid4().hex[:8]}"
        candidate_case_dir = Path(self.work_root) / candidate_id
        candidate_case_dir.mkdir(parents=True, exist_ok=True)

        geometry_path = candidate_case_dir / "input" / "candidate.stl"
        geometry_path.parent.mkdir(parents=True, exist_ok=True)
        geometry_path.write_bytes(trimesh.exchange.stl.export_stl(deformed))

        drag_proxy = _drag_proxy(deformed, self.region)
        volume_delta = _volume_delta(deformed, self._baseline_volume)

        try:
            manifest = self.build_case(
                candidate_case_dir,
                best_candidate_id=candidate_id,
                best_candidate_geometry_path=geometry_path,
            )
            run_manifest = self.run_case(
                candidate_case_dir / "working" / "openfoam_case",
                case_manifest=manifest,
                execute=True,
            )
        except Exception:
            return [_penalty_value(drag_proxy), volume_delta]

        status = run_manifest.get("status", "unknown")
        if status != "executed_ok":
            return [_penalty_value(drag_proxy), volume_delta]

        # Try to read real forceCoeffs drag; fall back to geometric proxy
        # when the file is missing (e.g. simpleFoam didn't run because the
        # case stops after snappyHexMesh).
        foam_case_dir = candidate_case_dir / "working" / "openfoam_case"
        cd_report = _read_force_coeffs(
            foam_case_dir,
            reference_velocity=self.reference_velocity_m_s,
            reference_area=self.reference_area_m2,
            fluid_density=self.fluid_density_kg_m3,
        )
        if cd_report is not None and cd_report.get("drag_newtons") is not None:
            return [float(cd_report["drag_newtons"]), volume_delta]
        if cd_report is not None:
            return [float(cd_report["final_cd"]), volume_delta]
        return [drag_proxy, volume_delta]


def _drag_proxy(mesh: trimesh.Trimesh, region: dict) -> float:
    extents = mesh.extents.astype(float)
    primary = int(region.get("axis_index", int(extents.argmax())))
    others = [i for i in range(3) if i != primary]
    axial = max(float(extents[primary]), 1e-9)
    beam = max(float(extents[others[0]]), 1e-9)
    draft = max(float(extents[others[1]]), 1e-9)
    return (beam * draft) / axial


def _volume_delta(mesh: trimesh.Trimesh, baseline_volume: float) -> float:
    candidate_volume = _mesh_volume(mesh)
    if baseline_volume <= 0:
        return 0.0
    return abs(candidate_volume - baseline_volume) / baseline_volume


def _mesh_volume(mesh: trimesh.Trimesh) -> float:
    if mesh.is_volume:
        return float(abs(mesh.volume))
    extents = mesh.extents.astype(float)
    return float(abs(extents[0] * extents[1] * extents[2]))


def _penalty_value(baseline_proxy: float) -> float:
    """Large finite penalty so NSGA-II demotes failed runs but still sorts."""
    return max(baseline_proxy * 1000.0, 1.0)


def _read_force_coeffs(
    foam_case_dir: Path,
    *,
    reference_velocity: float | None,
    reference_area: float | None,
    fluid_density: float | None,
) -> dict | None:
    """Locate and parse the latest forceCoeffs coefficient.dat, if any.

    OpenFOAM writes to ``postProcessing/forces/<startTime>/coefficient.dat``;
    for a steady-state simpleFoam run the directory name is usually ``0``
    but we pick the most recently modified one so the parser works for
    restarted cases too.
    """
    forces_root = foam_case_dir / "postProcessing" / "forces"
    if not forces_root.exists():
        return None
    subdirs = [p for p in forces_root.iterdir() if p.is_dir()]
    if not subdirs:
        return None
    latest = max(subdirs, key=lambda p: p.stat().st_mtime)
    dat_path = latest / "coefficient.dat"
    try:
        return parse_drag_coefficient_dat(
            dat_path,
            reference_velocity_m_s=reference_velocity,
            reference_area_m2=reference_area,
            fluid_density_kg_m3=fluid_density,
        )
    except (ForceCoeffsNotFoundError, ValueError):
        return None
