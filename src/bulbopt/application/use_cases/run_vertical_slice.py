from __future__ import annotations

from pathlib import Path

from bulbopt.application.contracts.models import CaseSummary, CreateCaseCommand
from bulbopt.application.use_cases.create_case import create_case
from bulbopt.domain.core.models import CaseStatus
from bulbopt.execution.checkpoints.file_checkpoint_store import FileCheckpointStore
from bulbopt.execution.logging.case_logger import CaseLogger
from bulbopt.execution.worker.local_worker import LocalWorker
from bulbopt.infrastructure.adapters.case_package_exporter import CasePackageExporter
from bulbopt.infrastructure.adapters.html_report import HtmlReportAdapter
from bulbopt.infrastructure.adapters.openfoam_adapter import OpenFOAMAdapter
from bulbopt.infrastructure.adapters.openfoam_runner import OpenFOAMRunnerAdapter
from bulbopt.infrastructure.adapters.stub_evaluation import StubEvaluationAdapter
from bulbopt.infrastructure.adapters.stub_geometry import StubGeometryAdapter
from bulbopt.infrastructure.adapters.stub_optimization import StubOptimizationAdapter
from bulbopt.storage.filesystem.json_store import JsonStore
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def run_vertical_slice(project_root: Path, command: CreateCaseCommand) -> CaseSummary:
    repository = FilesystemProjectRepository(root_dir=project_root)
    case = create_case(command=command, repository=repository)
    case_dir = repository.case_dir(case.case_id)
    return _execute_slice(repository=repository, case=case, case_dir=case_dir, command=command, resume=False)


def resume_vertical_slice(project_root: Path, case_id: str) -> CaseSummary:
    """Continue a recoverable case using the checkpoints saved by a prior run.

    Implements spec §10 Recovery quality criterion: the engineer must be able
    to restart the application and continue a case without manual filesystem
    repair. ``LocalWorker.run_strict(resume=True)`` skips stages whose
    ``completed`` checkpoints are intact and re-executes any failed stage.
    """
    repository = FilesystemProjectRepository(root_dir=project_root)
    case = repository.load_case(case_id)
    command = repository.load_create_case_command(case_id)
    case_dir = repository.case_dir(case_id)
    # Mark the case as re-opened — its final status will be rewritten by _execute_slice.
    case.is_recoverable = False
    case.status = CaseStatus.IMPORTED
    repository.save_case(case)
    return _execute_slice(repository=repository, case=case, case_dir=case_dir, command=command, resume=True)


def _execute_slice(
    *,
    repository: FilesystemProjectRepository,
    case,
    case_dir: Path,
    command: CreateCaseCommand,
    resume: bool,
) -> CaseSummary:
    json_store = JsonStore()
    geometry = StubGeometryAdapter()
    evaluation = StubEvaluationAdapter()
    optimization = StubOptimizationAdapter()
    openfoam = OpenFOAMAdapter()
    openfoam_runner = OpenFOAMRunnerAdapter()
    report = HtmlReportAdapter(template_root=_template_root())
    worker = LocalWorker(
        checkpoint_store=FileCheckpointStore(root_dir=case_dir / "working" / "checkpoints"),
    )
    case_logger = CaseLogger(case_dir / "logs" / "case.log")
    case_logger.log_stage(
        stage="pipeline",
        status="resumed" if resume else "started",
        extra={"case_id": case.case_id, "optimization_mode": command.optimization_mode},
    )

    def _tracked(stage_name: str, job):
        case_logger.log_stage(stage=stage_name, status="started")
        try:
            result = worker.run_strict(case.case_id, stage_name, job, resume=resume)
        except Exception as exc:
            case_logger.log_stage(
                stage=stage_name,
                status="failed",
                extra={"error": str(exc), "is_recoverable": True},
            )
            raise
        elapsed = _read_stage_elapsed(case_dir, case.case_id, stage_name)
        case_logger.log_stage(stage=stage_name, status="completed", elapsed_seconds=elapsed)
        return result

    try:
        bulb_region_override = {}
        if command.bulb_region_axis_min_override is not None:
            bulb_region_override["axis_min"] = command.bulb_region_axis_min_override
        if command.bulb_region_axis_max_override is not None:
            bulb_region_override["axis_max"] = command.bulb_region_axis_max_override
        bulb_region_override = bulb_region_override or None

        geometry_analysis = _tracked(
            "prepare_geometry",
            lambda: geometry.prepare_geometry(
                case_dir,
                Path(command.source_path),
                bulb_region_override=bulb_region_override,
            ),
        )
        candidates = _tracked(
            "generate_candidates",
            lambda: geometry.generate_candidates(
                case_dir,
                count=command.candidate_count,
                optimization_mode=command.optimization_mode,
            ),
        )
        repository.save_candidate_index(case.case_id, candidates)

        objective_weights = {
            "resistance_weight": command.resistance_weight,
            "axial_gain_weight": command.axial_gain_weight,
            "draft_reduction_weight": command.draft_reduction_weight,
            "beam_growth_weight": command.beam_growth_weight,
            "calm_water_condition_weight": command.calm_water_condition_weight,
            "wave_condition_weight": command.wave_condition_weight,
        }
        acceptability_thresholds = {
            "max_volume_delta_pct": command.max_volume_delta_pct,
            "max_draft_delta_m": command.max_draft_delta_m,
            "max_speed_balance_ratio": command.max_speed_balance_ratio,
            "max_wave_penalty": command.max_wave_penalty,
            "reject_volume_delta_pct": command.reject_volume_delta_pct,
            "reject_draft_delta_m": command.reject_draft_delta_m,
            "reject_speed_balance_ratio": command.reject_speed_balance_ratio,
            "reject_wave_penalty": command.reject_wave_penalty,
        }
        evaluated_candidates = _tracked(
            "evaluate_candidates",
            lambda: evaluation.evaluate_candidates(
                candidates,
                objective_weights=objective_weights,
                speed_knots=command.speed_knots,
                operational_profile_weights=command.operational_profile_weights,
                wave_height_m=command.wave_height_m,
                wave_period_s=command.wave_period_s,
                wave_scenario_heights_m=command.wave_scenario_heights_m,
                wave_scenario_periods_s=command.wave_scenario_periods_s,
                wave_scenario_weights=command.wave_scenario_weights,
                acceptability_thresholds=acceptability_thresholds,
            ),
        )
        evaluated_candidates = [_normalized_candidate(candidate) for candidate in evaluated_candidates]
        json_store.write(case_dir / "evaluation_index.json", evaluated_candidates)
        ranked_candidates = _tracked(
            "rank_candidates",
            lambda: optimization.rank_candidates(evaluated_candidates),
        )
        best_candidate = ranked_candidates[0]
        optimization_summary = optimization.summarize_ranking(evaluated_candidates)
        optimization_trace = optimization.build_trace(evaluated_candidates)
        high_fidelity_boundary = _tracked(
            "openfoam_build_case",
            lambda: openfoam.build_case(
                case_dir,
                best_candidate_id=best_candidate["candidate_id"],
                best_candidate_geometry_path=Path(best_candidate["geometry_path"]),
            ),
        )
        runner_summary = _tracked(
            "openfoam_run_case",
            lambda: openfoam_runner.run_case(
                case_dir / "working" / "openfoam_case",
                case_manifest=high_fidelity_boundary,
                execute=True,
            ),
        )
        high_fidelity_boundary.update(runner_summary)
        optimization_summary_path = case_dir / "working" / "evaluation" / "optimization_summary.json"
        json_store.write(optimization_summary_path, optimization_summary)
        artifacts_index_path = case_dir / "artifacts_index.json"
        artifacts_index = json_store.read(artifacts_index_path)
        artifacts_index["optimization_summary"] = str(optimization_summary_path)
        artifacts_index["best_candidate_stl"] = str(best_candidate["geometry_path"])
        artifacts_index["openfoam_case_manifest"] = str(case_dir / "working" / "openfoam_case" / "openfoam_case_manifest.json")
        artifacts_index["openfoam_run_manifest"] = str(case_dir / "working" / "openfoam_case" / "openfoam_run_manifest.json")
        json_store.write(artifacts_index_path, artifacts_index)
        timing_summary = _read_timing_summary(case_dir, case.case_id)
        case.summary_metrics = _build_case_summary_metrics(
            geometry_analysis=geometry_analysis,
            best_candidate=best_candidate,
            optimization_summary=optimization_summary,
            runtime_budget_hours=command.runtime_budget_hours,
            candidate_count=command.candidate_count,
            objective_weights=objective_weights,
            acceptability_thresholds=acceptability_thresholds,
            ranked_candidates=ranked_candidates,
            optimization_trace=optimization_trace,
            high_fidelity_boundary=high_fidelity_boundary,
            timing_summary=timing_summary,
        )
        case.status = CaseStatus.ASSEMBLING_RESULTS
        repository.save_case(case)
        _tracked(
            "build_html_report",
            lambda: str(report.build_html_report(
                case_dir,
                {
                    "case_name": case.case_name,
                    "status": _final_case_status(best_candidate).value,
                    "best_candidate_id": best_candidate["candidate_id"],
                    "best_candidate": best_candidate,
                    "ranked_candidates": ranked_candidates,
                    "optimization_summary": optimization_summary,
                    "runtime_budget_hours": command.runtime_budget_hours,
                    "candidate_count": command.candidate_count,
                    "processed_candidates": len(evaluated_candidates),
                    "objective_weights": objective_weights,
                    "acceptability_thresholds": acceptability_thresholds,
                    "optimization_trace": optimization_trace,
                    "repair_summary": _repair_summary_payload(geometry_analysis),
                    "bulb_region_summary": _bulb_region_summary_payload(geometry_analysis),
                    "before_after_summary": _before_after_summary_payload(
                        geometry_analysis=geometry_analysis,
                        best_candidate=best_candidate,
                    ),
                    "timing_summary": case.summary_metrics.get("timing", {}),
                    "operational_profile_summary": best_candidate.get("calm_water_metrics", {}),
                    "calm_water_summary": best_candidate.get("calm_water_metrics", {}),
                    "wave_response_summary": best_candidate.get("wave_response_metrics", {}),
                    "baseline_summary": case.summary_metrics.get("baseline", {}),
                    "multi_condition_summary": case.summary_metrics.get("multi_condition_objective", {}),
                    "selection_priority_summary": case.summary_metrics.get("selection_priority", {}),
                    "high_fidelity_boundary": case.summary_metrics.get("high_fidelity_boundary", {}),
                    "openfoam_available": case.summary_metrics.get("high_fidelity_boundary", {}).get("available", False),
                    "high_fidelity_used": case.summary_metrics.get("high_fidelity_boundary", {}).get("used", False),
                },
            )),
        )
        archive_path = _tracked(
            "export_case_package",
            lambda: str(
                CasePackageExporter().export(
                    case_dir,
                    case_dir / "outputs" / "packages",
                )
            ),
        )
        artifacts_index = json_store.read(artifacts_index_path)
        artifacts_index["case_package"] = archive_path
        json_store.write(artifacts_index_path, artifacts_index)

        # Refresh timing after the final two stages (report + export) have
        # written their checkpoints, so case.json captures the complete
        # stage list when the user opens it for observability.
        case.summary_metrics["timing"] = _read_timing_summary(case_dir, case.case_id)
        case.status = _final_case_status(best_candidate)
        case.is_recoverable = False
        repository.save_case(case)
        case_logger.log_stage(
            stage="pipeline",
            status=case.status.value,
            extra={"best_candidate_id": best_candidate["candidate_id"]},
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
        best_candidate_id=best_candidate["candidate_id"],
    )


def _template_root() -> Path:
    return Path(__file__).resolve().parents[2] / "reporting" / "templates"


def _final_case_status(best_candidate: dict) -> CaseStatus:
    acceptability = _normalized_acceptability(best_candidate)
    if acceptability.get("level") in {"warn", "reject"}:
        return CaseStatus.COMPLETED_WITH_WARNINGS
    return CaseStatus.COMPLETED


def _read_stage_elapsed(case_dir: Path, case_id: str, stage_name: str) -> float | None:
    """Return the last-written elapsed_seconds for a stage, or None if absent."""
    import json as _json

    checkpoint_path = case_dir / "working" / "checkpoints" / f"{case_id}-{stage_name}.json"
    if not checkpoint_path.exists():
        return None
    try:
        payload = _json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("elapsed_seconds")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_timing_summary(case_dir: Path, case_id: str) -> dict:
    """Aggregate per-stage elapsed_seconds from working/checkpoints/<case_id>-*.json.

    Stages that never ran yet are skipped. The total is computed only from
    completed stages so partial runs report accurate elapsed time.
    """
    import json as _json

    checkpoints_dir = case_dir / "working" / "checkpoints"
    stages: list[dict] = []
    total_seconds = 0.0
    if not checkpoints_dir.exists():
        return {"stages": stages, "total_seconds": 0.0, "stage_count": 0}

    prefix = f"{case_id}-"
    for checkpoint in sorted(checkpoints_dir.glob(f"{prefix}*.json")):
        try:
            payload = _json.loads(checkpoint.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        stage_name = checkpoint.stem[len(prefix):]
        elapsed = float(payload.get("elapsed_seconds") or 0.0)
        status = payload.get("status", "unknown")
        stages.append({"stage": stage_name, "status": status, "elapsed_seconds": round(elapsed, 6)})
        if status == "completed":
            total_seconds += elapsed

    # Also note the slowest stage for the UI "where did the time go" read.
    slowest_stage = max(
        (stage for stage in stages if stage["status"] == "completed"),
        key=lambda item: item["elapsed_seconds"],
        default=None,
    )
    return {
        "stages": stages,
        "total_seconds": round(total_seconds, 6),
        "stage_count": len(stages),
        "slowest_stage": slowest_stage["stage"] if slowest_stage else None,
        "slowest_stage_seconds": slowest_stage["elapsed_seconds"] if slowest_stage else None,
    }


def _build_case_summary_metrics(
    geometry_analysis: dict,
    best_candidate: dict,
    optimization_summary: dict,
    runtime_budget_hours: int,
    candidate_count: int,
    objective_weights: dict[str, float],
    acceptability_thresholds: dict[str, float],
    ranked_candidates: list[dict],
    optimization_trace: dict[str, str | list[str]],
    high_fidelity_boundary: dict[str, bool | str],
    timing_summary: dict | None = None,
) -> dict:
    quality_report = geometry_analysis.get("quality_report", {})
    geometry_metrics = best_candidate.get("geometry_metrics", {})
    hydrostatics_metrics = best_candidate.get("hydrostatics_metrics", {})
    calm_water_metrics = best_candidate.get("calm_water_metrics", {})
    wave_response_metrics = best_candidate.get("wave_response_metrics", {})
    multi_condition_objective = best_candidate.get("multi_condition_objective", {})
    selection_priority = best_candidate.get("selection_priority", {})
    acceptability = _normalized_acceptability(best_candidate)
    score_components = best_candidate.get("score_components", {})
    candidate_rows = [
        (
            f"{item.get('candidate_id', 'n/a')} | "
            f"level={item.get('acceptability', {}).get('level', 'n/a')} | "
            f"fast={item.get('fast_score', 'n/a')} | "
            f"mid={item.get('mid_score', 'n/a')} | "
            f"resistance={item.get('score_components', {}).get('resistance_proxy', 'n/a')} | "
            f"hydro={item.get('score_components', {}).get('hydrostatic_penalty', 'n/a')} | "
            f"calm={item.get('score_components', {}).get('calm_water_penalty', 'n/a')} | "
            f"wave={item.get('score_components', {}).get('wave_penalty', 'n/a')} | "
            f"reasons={','.join(item.get('acceptability', {}).get('reasons', [])) or 'none'}"
        )
        for item in ranked_candidates
    ]
    candidate_summary = "Candidates summary: not available"
    if ranked_candidates:
        candidate_summary = "Candidates: " + " | ".join(
            f"{item.get('candidate_id', 'n/a')} mid={item.get('mid_score', 'n/a')}"
            for item in ranked_candidates
        )
    rejected_candidates = [
        item for item in ranked_candidates if item.get("acceptability", {}).get("level") == "reject"
    ]
    rejected_summary = "Rejected candidates: none"
    rejected_rows = [
        (
            f"{item.get('candidate_id', 'n/a')} | "
                        f"level=reject | "
                        f"resistance={item.get('score_components', {}).get('resistance_proxy', 'n/a')} | "
                        f"hydro={item.get('score_components', {}).get('hydrostatic_penalty', 'n/a')} | "
                        f"calm={item.get('score_components', {}).get('calm_water_penalty', 'n/a')} | "
                        f"wave={item.get('score_components', {}).get('wave_penalty', 'n/a')} | "
                        f"reasons={','.join(item.get('acceptability', {}).get('reasons', [])) or 'none'}"
                    )
        for item in rejected_candidates
    ]
    if rejected_candidates:
        rejected_summary = "Rejected candidates: " + " | ".join(
            f"{item.get('candidate_id', 'n/a')} reasons={','.join(item.get('acceptability', {}).get('reasons', [])) or 'none'}"
            for item in rejected_candidates
        )

    return {
        "geometry": {
            "vertices_count": quality_report.get("vertices_count"),
            "faces_count": quality_report.get("faces_count"),
            "watertight": quality_report.get("watertight"),
            "primary_axis": quality_report.get("primary_axis"),
            "slenderness_ratio": geometry_metrics.get("slenderness_ratio"),
        },
        "evaluation": {
            "best_candidate_id": best_candidate.get("candidate_id"),
            "best_candidate_geometry_path": best_candidate.get("geometry_path"),
            "fast_score": best_candidate.get("fast_score"),
            "mid_score": best_candidate.get("mid_score"),
            "resistance_proxy": score_components.get("resistance_proxy"),
        },
        "hydrostatics": {
            "volume_delta_pct": hydrostatics_metrics.get("volume_delta_pct"),
            "draft_delta_m": hydrostatics_metrics.get("draft_delta_m"),
            "hydrostatic_penalty": score_components.get("hydrostatic_penalty"),
            "constraint_status": hydrostatics_metrics.get("constraint_status"),
            "warnings": hydrostatics_metrics.get("warnings", []),
        },
        "operational_profile": {
            "profile_source": calm_water_metrics.get("profile_source"),
            "dominant_speed_knots": calm_water_metrics.get("dominant_speed_knots"),
            "speed_knots": calm_water_metrics.get("speed_knots", []),
            "operational_profile_weights": calm_water_metrics.get("operational_profile_weights", []),
        },
        "calm_water": {
            "surrogate_model": calm_water_metrics.get("surrogate_model"),
            "mean_froude_number": calm_water_metrics.get("mean_froude_number"),
            "speed_count": calm_water_metrics.get("speed_count"),
            "mean_resistance_proxy": calm_water_metrics.get("mean_resistance_proxy"),
            "mean_power_proxy_kw": calm_water_metrics.get("mean_power_proxy_kw"),
            "mean_effective_power_proxy_kw": calm_water_metrics.get("mean_effective_power_proxy_kw"),
            "mean_fuel_proxy_kgph": calm_water_metrics.get("mean_fuel_proxy_kgph"),
            "aggregate_resistance_proxy": calm_water_metrics.get("aggregate_resistance_proxy"),
            "aggregate_power_proxy_kw": calm_water_metrics.get("aggregate_power_proxy_kw"),
            "aggregate_effective_power_proxy_kw": calm_water_metrics.get("aggregate_effective_power_proxy_kw"),
            "aggregate_fuel_proxy_kgph": calm_water_metrics.get("aggregate_fuel_proxy_kgph"),
            "reference_aggregate_resistance_proxy": calm_water_metrics.get("reference_aggregate_resistance_proxy"),
            "reference_aggregate_power_proxy_kw": calm_water_metrics.get("reference_aggregate_power_proxy_kw"),
            "reference_aggregate_effective_power_proxy_kw": calm_water_metrics.get("reference_aggregate_effective_power_proxy_kw"),
            "reference_aggregate_fuel_proxy_kgph": calm_water_metrics.get("reference_aggregate_fuel_proxy_kgph"),
            "resistance_improvement_pct": calm_water_metrics.get("resistance_improvement_pct"),
            "power_improvement_pct": calm_water_metrics.get("power_improvement_pct"),
            "effective_power_improvement_pct": calm_water_metrics.get("effective_power_improvement_pct"),
            "fuel_improvement_pct": calm_water_metrics.get("fuel_improvement_pct"),
            "dominant_speed_knots": calm_water_metrics.get("dominant_speed_knots"),
            "calm_water_penalty": score_components.get("calm_water_penalty"),
        },
        "wave_response": {
            "wave_height_m": wave_response_metrics.get("wave_height_m"),
            "wave_period_s": wave_response_metrics.get("wave_period_s"),
            "scenario_source": wave_response_metrics.get("scenario_source"),
            "scenario_count": wave_response_metrics.get("scenario_count"),
            "scenario_rows": wave_response_metrics.get("scenario_rows", []),
            "dominant_scenario_label": wave_response_metrics.get("dominant_scenario_label"),
            "added_resistance_proxy": wave_response_metrics.get("added_resistance_proxy"),
            "added_power_proxy_kw": wave_response_metrics.get("added_power_proxy_kw"),
            "wave_penalty": score_components.get("wave_penalty"),
            "condition_status": wave_response_metrics.get("condition_status"),
        },
        "multi_condition_objective": {
            "combined_penalty": multi_condition_objective.get("combined_penalty"),
            "combined_objective_score": multi_condition_objective.get("combined_objective_score"),
            "dominant_condition": multi_condition_objective.get("dominant_condition"),
            "calm_water_weight": multi_condition_objective.get("calm_water_weight"),
            "wave_response_weight": multi_condition_objective.get("wave_response_weight"),
        },
        "selection_priority": {
            "calibration_model": selection_priority.get("calibration_model"),
            "selection_priority_score": selection_priority.get("selection_priority_score"),
            "cfd_focus_band": selection_priority.get("cfd_focus_band"),
            "aggregate_effective_power_proxy_kw": selection_priority.get("aggregate_effective_power_proxy_kw"),
            "hydrostatic_penalty": selection_priority.get("hydrostatic_penalty"),
            "wave_penalty": selection_priority.get("wave_penalty"),
            "combined_penalty": selection_priority.get("combined_penalty"),
        },
        "baseline": {
            "reference_aggregate_resistance_proxy": calm_water_metrics.get("reference_aggregate_resistance_proxy"),
            "reference_aggregate_power_proxy_kw": calm_water_metrics.get("reference_aggregate_power_proxy_kw"),
            "reference_aggregate_fuel_proxy_kgph": calm_water_metrics.get("reference_aggregate_fuel_proxy_kgph"),
            "resistance_improvement_pct": calm_water_metrics.get("resistance_improvement_pct"),
            "power_improvement_pct": calm_water_metrics.get("power_improvement_pct"),
            "fuel_improvement_pct": calm_water_metrics.get("fuel_improvement_pct"),
            "reference_vs_candidate": "stable" if acceptability.get("is_acceptable", True) else "review_required",
        },
        "acceptability": {
            "is_acceptable": acceptability.get("is_acceptable", True),
            "level": acceptability.get("level", "ok"),
            "hydrostatics_status": acceptability.get("hydrostatics_status", hydrostatics_metrics.get("constraint_status", "ok")),
            "operational_profile_status": acceptability.get("operational_profile_status", "ok"),
            "wave_response_status": acceptability.get("wave_response_status", "ok"),
            "reasons": acceptability.get("reasons", []),
        },
        "acceptability_thresholds": acceptability_thresholds,
        "execution": {
            "runtime_budget_hours": runtime_budget_hours,
            "candidate_count": candidate_count,
            "processed_candidates": len(ranked_candidates),
        },
        "objective_weights": objective_weights,
        "optimization": optimization_summary,
        "optimization_trace": optimization_trace,
        "candidates": {
            "summary": candidate_summary,
            "rows": candidate_rows,
        },
        "rejected_candidates": {
            "summary": rejected_summary,
            "rows": rejected_rows,
        },
        "high_fidelity_boundary": high_fidelity_boundary,
        "timing": timing_summary or {"stages": [], "total_seconds": 0.0, "stage_count": 0},
    }


def _normalized_acceptability(best_candidate: dict) -> dict:
    acceptability = dict(best_candidate.get("acceptability", {}))
    if "level" in acceptability:
        return acceptability

    hydrostatics = best_candidate.get("hydrostatics_metrics", {})
    hydro_status = hydrostatics.get("constraint_status", "ok")
    if hydro_status in {"warn", "reject"}:
        return {
            "is_acceptable": hydro_status != "reject",
            "level": hydro_status,
            "hydrostatics_status": hydro_status,
            "operational_profile_status": "ok",
            "wave_response_status": "ok",
            "reasons": ["hydrostatics_warn"],
        }

    return {
        "is_acceptable": acceptability.get("is_acceptable", True),
        "level": "ok" if acceptability.get("is_acceptable", True) else "reject",
        "hydrostatics_status": acceptability.get("hydrostatics_status", "ok"),
        "operational_profile_status": acceptability.get("operational_profile_status", "ok"),
        "wave_response_status": acceptability.get("wave_response_status", "ok"),
        "reasons": acceptability.get("reasons", []),
    }


def _normalized_candidate(candidate: dict) -> dict:
    normalized = dict(candidate)
    normalized["acceptability"] = _normalized_acceptability(candidate)
    return normalized


def _before_after_summary_payload(
    *,
    geometry_analysis: dict,
    best_candidate: dict,
) -> dict:
    """Spec §14: before/after visual comparison. Keep it numeric for the first
    slice — baseline stats come from the repaired mesh's quality_report, and
    best-candidate stats come from geometry_metrics.
    """
    quality_report = geometry_analysis.get("quality_report", {})
    geometry_metrics = best_candidate.get("geometry_metrics", {})
    baseline_extents = quality_report.get("extents") or [0.0, 0.0, 0.0]
    primary_axis = int(quality_report.get("primary_axis", 0))
    secondary_axes = [idx for idx in range(3) if idx != primary_axis]
    baseline_axial = float(baseline_extents[primary_axis]) if len(baseline_extents) == 3 else 0.0
    baseline_beam = float(baseline_extents[secondary_axes[0]]) if len(baseline_extents) == 3 else 0.0
    baseline_draft = float(baseline_extents[secondary_axes[1]]) if len(baseline_extents) == 3 else 0.0
    candidate_axial = float(geometry_metrics.get("axial_extent_m", 0.0))
    candidate_beam = float(geometry_metrics.get("beam_extent_m", 0.0))
    candidate_draft = float(geometry_metrics.get("draft_extent_m", 0.0))
    baseline_surface = float(quality_report.get("surface_area", 0.0))
    candidate_surface = float(geometry_metrics.get("surface_area_m2", 0.0))

    def _pct_delta(baseline: float, candidate: float) -> float:
        if baseline <= 0.0:
            return 0.0
        return round(((candidate - baseline) / baseline) * 100.0, 3)

    return {
        "baseline": {
            "vertices_count": quality_report.get("vertices_count"),
            "faces_count": quality_report.get("faces_count"),
            "watertight": quality_report.get("watertight"),
            "axial_extent_m": baseline_axial,
            "beam_extent_m": baseline_beam,
            "draft_extent_m": baseline_draft,
            "surface_area_m2": baseline_surface,
            "volume_m3": quality_report.get("volume"),
        },
        "best_candidate": {
            "candidate_id": best_candidate.get("candidate_id"),
            "axial_extent_m": candidate_axial,
            "beam_extent_m": candidate_beam,
            "draft_extent_m": candidate_draft,
            "surface_area_m2": candidate_surface,
            "slenderness_ratio": geometry_metrics.get("slenderness_ratio"),
        },
        "delta": {
            "axial_extent_pct": _pct_delta(baseline_axial, candidate_axial),
            "beam_extent_pct": _pct_delta(baseline_beam, candidate_beam),
            "draft_extent_pct": _pct_delta(baseline_draft, candidate_draft),
            "surface_area_pct": _pct_delta(baseline_surface, candidate_surface),
            "axial_gain_m": geometry_metrics.get("axial_gain_m"),
            "beam_growth_m": geometry_metrics.get("beam_growth_m"),
            "draft_reduction_m": geometry_metrics.get("draft_reduction_m"),
        },
    }


def _bulb_region_summary_payload(geometry_analysis: dict) -> dict:
    bulb_region = geometry_analysis.get("bulb_region", {})
    return {
        "axis_index": bulb_region.get("axis_index"),
        "axis_min": bulb_region.get("axis_min"),
        "axis_max": bulb_region.get("axis_max"),
        "auto_axis_min": bulb_region.get("auto_axis_min"),
        "auto_axis_max": bulb_region.get("auto_axis_max"),
        "confirmation_source": bulb_region.get("confirmation_source", "auto_detected"),
        "mask_ratio": bulb_region.get("mask_ratio"),
    }


def _repair_summary_payload(geometry_analysis: dict) -> dict:
    quality_report = geometry_analysis.get("quality_report", {})
    return {
        "repair_status": quality_report.get("repair_status", "not_needed"),
        "repaired": quality_report.get("repaired", False),
        "watertight": quality_report.get("watertight"),
        "watertight_before": quality_report.get("watertight_before"),
        "vertices_count": quality_report.get("vertices_count"),
        "faces_count": quality_report.get("faces_count"),
        "vertices_count_before": quality_report.get("vertices_count_before"),
        "faces_count_before": quality_report.get("faces_count_before"),
    }
