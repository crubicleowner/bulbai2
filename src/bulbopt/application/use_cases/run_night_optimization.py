"""``run_night_optimization`` — night-run entry point.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §11.

End-to-end flow:

  1. Create a new case and persist the source STL via the existing
     ``create_case`` use case.
  2. Run ``prepare_geometry`` once to detect the bulb region and write
     ``working/repaired/repaired.stl``.
  3. Build a cascade:
       * mid gate = cheap mesh-derived proxy (slenderness vs. volume)
       * high gate = caller-supplied (defaults to a numeric proxy)
     NSGA-II explores the Kracht space, the scheduler tracks time.
  4. Persist:
       * ``working/night_optimization/pareto_front.json``
       * ``working/night_optimization/high_fidelity_results.json``
       * ``working/night_optimization/budget_trace.json``
  5. Export the top-ranked high-fidelity STL + each Pareto candidate STL
     under ``outputs/top_candidates/candidate-XXX/``.
  6. Update the case to ``completed`` / ``completed_with_warnings`` and
     return a ``CaseSummary`` pointing at the winner.

The default high-fidelity evaluator is a parameter-only proxy (identical
in cost to mid gate) so unit tests run in milliseconds. The real
``simple_foam_runner`` replaces this evaluator in Task 6.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Sequence

import trimesh

from bulbopt.application.contracts.models import CaseSummary, CreateCaseCommand
from bulbopt.application.use_cases.create_case import create_case
from bulbopt.domain.core.models import CaseStatus
from bulbopt.execution.logging.case_logger import CaseLogger
from bulbopt.infrastructure.adapters.html_report import HtmlReportAdapter
from bulbopt.infrastructure.adapters.openfoam_adapter import (
    OpenFOAMAdapter,
    detect_openfoam_available,
)
from bulbopt.infrastructure.adapters.openfoam_runner import OpenFOAMRunnerAdapter
from bulbopt.infrastructure.adapters.simple_foam_gate import SimpleFoamHighFidelityGate
from bulbopt.infrastructure.adapters.stub_geometry import StubGeometryAdapter
from bulbopt.optimization.parametric.ffd_deformer import BulbFFDDeformer
from bulbopt.optimization.parametric.kracht_space import (
    KRACHT_PARAMETER_NAMES,
    KrachtDesignSpace,
    KrachtVector,
)
from bulbopt.optimization.scheduler.budget_scheduler import BudgetScheduler
from bulbopt.optimization.strategies.cascade_strategy import (
    CascadeResult,
    CascadeStrategy,
    Gate,
)
from bulbopt.storage.filesystem.json_store import JsonStore
from bulbopt.storage.project_repository.filesystem_repository import (
    FilesystemProjectRepository,
)


HighFidelityEvaluator = Callable[[List[KrachtVector]], List[List[float]]]


@dataclass(slots=True)
class NightOptimizationConfig:
    """All the knobs for a night run that aren't in CreateCaseCommand."""
    population: int = 50
    generations: int = 20
    high_fidelity_budget: int = 10
    runtime_budget_hours: float = 8.0
    seed: int | None = None
    mid_gate_estimated_seconds_per_eval: float = 5.0
    high_gate_estimated_seconds_per_eval: float = 300.0


def run_night_optimization(
    *,
    project_root: Path,
    command: CreateCaseCommand,
    config: NightOptimizationConfig | None = None,
    high_fidelity_evaluator: HighFidelityEvaluator | None = None,
) -> CaseSummary:
    config = config or NightOptimizationConfig()
    repository = FilesystemProjectRepository(root_dir=project_root)
    case = create_case(command=command, repository=repository)
    case_dir = repository.case_dir(case.case_id)
    json_store = JsonStore()
    case_logger = CaseLogger(case_dir / "logs" / "case.log")
    case_logger.log_stage(
        stage="pipeline",
        status="started",
        extra={"case_id": case.case_id, "mode": "night_optimization"},
    )

    try:
        # Stage 1: prepare base geometry.
        case_logger.log_stage(stage="prepare_geometry", status="started")
        geometry = StubGeometryAdapter()
        geometry_analysis = geometry.prepare_geometry(case_dir, Path(command.source_path))
        case_logger.log_stage(stage="prepare_geometry", status="completed")

        # Stage 2: cascade.
        case_logger.log_stage(stage="night_optimization", status="started")
        space = KrachtDesignSpace()
        deformer = BulbFFDDeformer()
        repaired_mesh = trimesh.load(
            case_dir / "working" / "repaired" / "repaired.stl",
            force="mesh",
        )
        region = geometry_analysis["bulb_region"]

        mid_gate = Gate(
            name="mid",
            evaluate=_mid_gate_evaluator(repaired_mesh, region, deformer),
            estimated_seconds_per_eval=config.mid_gate_estimated_seconds_per_eval,
        )
        if high_fidelity_evaluator is not None:
            high_eval = high_fidelity_evaluator
        elif detect_openfoam_available():
            case_logger.log_stage(
                stage="high_gate",
                status="initialised",
                extra={"backend": "simple_foam"},
            )
            foam_work_root = case_dir / "working" / "night_optimization" / "foam_candidates"
            foam_work_root.mkdir(parents=True, exist_ok=True)
            builder = OpenFOAMAdapter()
            runner = OpenFOAMRunnerAdapter()
            foam_gate = SimpleFoamHighFidelityGate(
                work_root=foam_work_root,
                baseline_mesh=repaired_mesh,
                region=region,
                deformer=deformer,
                build_case=builder.build_case,
                run_case=runner.run_case,
            )
            high_eval = foam_gate.evaluate
        else:
            case_logger.log_stage(
                stage="high_gate",
                status="initialised",
                extra={"backend": "surrogate", "reason": "openfoam_unavailable"},
            )
            high_eval = _default_high_evaluator(repaired_mesh, region, deformer)
        high_gate = Gate(
            name="high",
            evaluate=high_eval,
            estimated_seconds_per_eval=config.high_gate_estimated_seconds_per_eval,
        )

        scheduler = BudgetScheduler(runtime_budget_hours=config.runtime_budget_hours)
        cascade = CascadeStrategy(
            space=space,
            scheduler=scheduler,
            population=config.population,
            generations=config.generations,
            high_fidelity_budget=config.high_fidelity_budget,
            mid_gate=mid_gate,
            high_gate=high_gate,
            seed=config.seed,
        )
        result: CascadeResult = cascade.run()
        case_logger.log_stage(
            stage="night_optimization",
            status="completed",
            extra={
                "pareto_candidates": len(result.pareto_front.candidates),
                "high_fidelity_candidates": len(result.high_fidelity_results),
                "budget_exhausted": result.budget_exhausted,
            },
        )

        # Stage 3: persist outputs.
        night_dir = case_dir / "working" / "night_optimization"
        night_dir.mkdir(parents=True, exist_ok=True)
        json_store.write(
            night_dir / "pareto_front.json",
            {
                "candidates": [
                    {
                        "vector": [
                            candidate.vector.values[name]
                            for name in KRACHT_PARAMETER_NAMES
                        ],
                        "parameters": dict(candidate.vector.values),
                        "objectives": list(candidate.objectives),
                    }
                    for candidate in result.pareto_front.candidates
                ],
            },
        )
        json_store.write(
            night_dir / "high_fidelity_results.json",
            {
                "results": [
                    {
                        "vector": [r.vector.values[name] for name in KRACHT_PARAMETER_NAMES],
                        "parameters": dict(r.vector.values),
                        "objectives": list(r.objectives),
                    }
                    for r in result.high_fidelity_results
                ],
            },
        )
        json_store.write(
            night_dir / "budget_trace.json",
            {
                "trace": scheduler.trace(),
                "gate_timings": scheduler.gate_timings(),
                "runtime_budget_hours": config.runtime_budget_hours,
                "remaining_seconds": scheduler.remaining_seconds,
                "budget_exhausted": result.budget_exhausted,
            },
        )

        # Stage 4: write STL per top candidate + pick winner.
        winner_id = _persist_top_candidate_meshes(
            case_dir=case_dir,
            result=result,
            repaired_mesh=repaired_mesh,
            region=region,
            deformer=deformer,
        )
        case_logger.log_stage(
            stage="night_optimization_outputs",
            status="completed",
            extra={"winner": winner_id or "n/a"},
        )

        # Stage 5: render the HTML night-run report.
        try:
            _render_night_report(
                case_dir=case_dir,
                command=command,
                config=config,
                result=result,
                scheduler=scheduler,
                winner_id=winner_id,
                high_gate_backend=(
                    "simple_foam"
                    if high_fidelity_evaluator is None and detect_openfoam_available()
                    else ("external" if high_fidelity_evaluator is not None else "surrogate")
                ),
            )
            case_logger.log_stage(
                stage="build_night_report",
                status="completed",
                extra={"path": str(case_dir / "outputs" / "reports" / "night_report.html")},
            )
        except Exception as report_error:
            case_logger.log_stage(
                stage="build_night_report",
                status="failed",
                extra={"error": str(report_error)},
            )

        case.status = (
            CaseStatus.COMPLETED_WITH_WARNINGS
            if result.budget_exhausted
            else CaseStatus.COMPLETED
        )
        case.is_recoverable = False
        case.summary_metrics = {
            "night_optimization": {
                "pareto_size": len(result.pareto_front.candidates),
                "high_fidelity_size": len(result.high_fidelity_results),
                "budget_exhausted": result.budget_exhausted,
                "winner_id": winner_id,
                "gate_timings": scheduler.gate_timings(),
            }
        }
        repository.save_case(case)
        case_logger.log_stage(
            stage="pipeline",
            status=case.status.value,
            extra={"winner": winner_id or "n/a"},
        )
    except Exception as exc:
        case.status = CaseStatus.FAILED
        case.is_recoverable = True
        repository.save_case(case)
        case_logger.log_stage(
            stage="pipeline",
            status="failed",
            extra={"error": str(exc), "is_recoverable": True},
        )
        raise

    return CaseSummary(
        case_id=case.case_id,
        case_name=case.case_name,
        status=case.status.value,
        best_candidate_id=winner_id,
    )


# --- gates ---------------------------------------------------------------


def _mid_gate_evaluator(
    baseline_mesh: trimesh.Trimesh,
    region: dict,
    deformer: BulbFFDDeformer,
) -> Callable[[Sequence[KrachtVector]], List[List[float]]]:
    """Mid-fidelity proxy: deform mesh, read slenderness + volume delta."""

    baseline_volume = _mesh_volume(baseline_mesh)

    def evaluate(vectors: Sequence[KrachtVector]) -> List[List[float]]:
        objectives: List[List[float]] = []
        for vector in vectors:
            deformed = deformer.deform(baseline_mesh, region, vector)
            extents = deformed.extents.astype(float)
            primary = int(region.get("axis_index", int(extents.argmax())))
            secondary = [i for i in range(3) if i != primary]
            axial = max(extents[primary], 1e-9)
            beam = max(extents[secondary[0]], 1e-9)
            draft = max(extents[secondary[1]], 1e-9)
            # Resistance proxy (smaller is better): wider & deeper bulbs
            # trade drag for volume.
            resistance_proxy = (beam * draft) / axial
            # Volume delta (preserve displacement). Smaller abs is better.
            deformed_volume = _mesh_volume(deformed)
            volume_delta = abs(deformed_volume - baseline_volume) / max(baseline_volume, 1e-6)
            objectives.append([float(resistance_proxy), float(volume_delta)])
        return objectives

    return evaluate


def _default_high_evaluator(
    baseline_mesh: trimesh.Trimesh,
    region: dict,
    deformer: BulbFFDDeformer,
) -> Callable[[Sequence[KrachtVector]], List[List[float]]]:
    """Placeholder high-fidelity gate: same proxy as mid for fast tests.
    Task 6 replaces this with a simpleFoam runner."""
    return _mid_gate_evaluator(baseline_mesh, region, deformer)


# --- persistence helpers ------------------------------------------------


def _persist_top_candidate_meshes(
    *,
    case_dir: Path,
    result: CascadeResult,
    repaired_mesh: trimesh.Trimesh,
    region: dict,
    deformer: BulbFFDDeformer,
) -> str | None:
    output_root = case_dir / "outputs" / "top_candidates"
    output_root.mkdir(parents=True, exist_ok=True)

    ranked = list(result.high_fidelity_results) or [
        type(
            "_CandidateAsResult",
            (),
            {"vector": candidate.vector, "objectives": candidate.objectives},
        )()
        for candidate in result.pareto_front.candidates
    ]
    winner_id: str | None = None
    for index, candidate in enumerate(ranked[:10], start=1):
        candidate_id = f"candidate-{index:03d}"
        if winner_id is None:
            winner_id = candidate_id
        candidate_dir = output_root / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        deformed = deformer.deform(repaired_mesh, region, candidate.vector)
        (candidate_dir / "geometry.stl").write_bytes(
            trimesh.exchange.stl.export_stl(deformed)
        )
    return winner_id


def _render_night_report(
    *,
    case_dir: Path,
    command: CreateCaseCommand,
    config: NightOptimizationConfig,
    result,
    scheduler,
    winner_id: str | None,
    high_gate_backend: str,
) -> Path:
    template_root = Path(__file__).resolve().parents[2] / "reporting" / "templates"
    report = HtmlReportAdapter(template_root=template_root)
    reports_dir = case_dir / "outputs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    pareto_candidates = []
    for c in result.pareto_front.candidates:
        pareto_candidates.append(
            {
                "parameters": dict(c.vector.values),
                "objectives": list(c.objectives),
            }
        )

    high_fidelity = []
    for index, r in enumerate(result.high_fidelity_results, start=1):
        candidate_id = f"candidate-{index:03d}"
        stl_path = case_dir / "outputs" / "top_candidates" / candidate_id / "geometry.stl"
        high_fidelity.append(
            {
                "parameters": dict(r.vector.values),
                "objectives": list(r.objectives),
                "stl_path": str(stl_path.relative_to(case_dir)),
            }
        )

    status = (
        "completed_with_warnings" if result.budget_exhausted else "completed"
    )
    context = {
        "case_name": command.case_name,
        "status": status,
        "winner_id": winner_id,
        "runtime_budget_hours": config.runtime_budget_hours,
        "population": config.population,
        "generations": config.generations,
        "high_fidelity_budget": config.high_fidelity_budget,
        "pareto_size": len(pareto_candidates),
        "high_fidelity_size": len(high_fidelity),
        "budget_exhausted": result.budget_exhausted,
        "gate_timings": scheduler.gate_timings(),
        "pareto_candidates": pareto_candidates,
        "high_fidelity": high_fidelity,
        "budget_trace": scheduler.trace(),
        "high_gate_backend": high_gate_backend,
        "parameter_names": list(KRACHT_PARAMETER_NAMES),
    }

    # The HtmlReportAdapter writes report.html via a hard-coded template
    # name; for the night report we render via its raw Jinja environment
    # and write to night_report.html beside it.
    template = report.environment.get_template("night_report.html.j2")
    output_path = reports_dir / "night_report.html"
    output_path.write_text(template.render(**context), encoding="utf-8")
    return output_path


def _mesh_volume(mesh: trimesh.Trimesh) -> float:
    if mesh.is_volume:
        return float(abs(mesh.volume))
    # fall back to AABB volume so non-watertight meshes still produce a
    # finite "volume proxy" without crashing.
    extents = mesh.extents.astype(float)
    return float(abs(extents[0] * extents[1] * extents[2]))
