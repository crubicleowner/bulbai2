from __future__ import annotations

from pathlib import Path

from bulbopt.application.contracts.models import CaseSummary, CreateCaseCommand
from bulbopt.application.use_cases.create_case import create_case
from bulbopt.domain.core.models import CaseStatus
from bulbopt.infrastructure.adapters.html_report import HtmlReportAdapter
from bulbopt.infrastructure.adapters.openfoam_adapter import OpenFOAMAdapter
from bulbopt.infrastructure.adapters.stub_evaluation import StubEvaluationAdapter
from bulbopt.infrastructure.adapters.stub_geometry import StubGeometryAdapter
from bulbopt.infrastructure.adapters.stub_optimization import StubOptimizationAdapter
from bulbopt.storage.filesystem.json_store import JsonStore
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def run_vertical_slice(project_root: Path, command: CreateCaseCommand) -> CaseSummary:
    repository = FilesystemProjectRepository(root_dir=project_root)
    json_store = JsonStore()
    case = create_case(command=command, repository=repository)
    case_dir = repository.case_dir(case.case_id)

    geometry = StubGeometryAdapter()
    evaluation = StubEvaluationAdapter()
    optimization = StubOptimizationAdapter()
    openfoam = OpenFOAMAdapter()
    report = HtmlReportAdapter(template_root=_template_root())

    try:
        geometry_analysis = geometry.prepare_geometry(case_dir, Path(command.source_path))
        candidates = geometry.generate_candidates(case_dir, count=command.candidate_count)
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
        evaluated_candidates = evaluation.evaluate_candidates(
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
        )
        evaluated_candidates = [_normalized_candidate(candidate) for candidate in evaluated_candidates]
        json_store.write(case_dir / "evaluation_index.json", evaluated_candidates)
        ranked_candidates = optimization.rank_candidates(evaluated_candidates)
        best_candidate = ranked_candidates[0]
        optimization_summary = optimization.summarize_ranking(evaluated_candidates)
        optimization_trace = optimization.build_trace(evaluated_candidates)
        optimization_summary_path = case_dir / "working" / "evaluation" / "optimization_summary.json"
        json_store.write(optimization_summary_path, optimization_summary)
        artifacts_index_path = case_dir / "artifacts_index.json"
        artifacts_index = json_store.read(artifacts_index_path)
        artifacts_index["optimization_summary"] = str(optimization_summary_path)
        artifacts_index["best_candidate_stl"] = str(best_candidate["geometry_path"])
        json_store.write(artifacts_index_path, artifacts_index)
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
            high_fidelity_boundary=openfoam.boundary_summary(),
        )
        case.status = CaseStatus.ASSEMBLING_RESULTS
        repository.save_case(case)
        report.build_html_report(
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
                "operational_profile_summary": best_candidate.get("calm_water_metrics", {}),
                "calm_water_summary": best_candidate.get("calm_water_metrics", {}),
                "wave_response_summary": best_candidate.get("wave_response_metrics", {}),
                "baseline_summary": case.summary_metrics.get("baseline", {}),
                "multi_condition_summary": case.summary_metrics.get("multi_condition_objective", {}),
                "high_fidelity_boundary": case.summary_metrics.get("high_fidelity_boundary", {}),
                "openfoam_available": case.summary_metrics.get("high_fidelity_boundary", {}).get("available", False),
                "high_fidelity_used": case.summary_metrics.get("high_fidelity_boundary", {}).get("used", False),
            },
        )
        case.status = _final_case_status(best_candidate)
        case.is_recoverable = False
        repository.save_case(case)
    except Exception:
        case.status = CaseStatus.FAILED
        case.is_recoverable = True
        repository.save_case(case)
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
) -> dict:
    quality_report = geometry_analysis.get("quality_report", {})
    geometry_metrics = best_candidate.get("geometry_metrics", {})
    hydrostatics_metrics = best_candidate.get("hydrostatics_metrics", {})
    calm_water_metrics = best_candidate.get("calm_water_metrics", {})
    wave_response_metrics = best_candidate.get("wave_response_metrics", {})
    multi_condition_objective = best_candidate.get("multi_condition_objective", {})
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
            "speed_count": calm_water_metrics.get("speed_count"),
            "mean_resistance_proxy": calm_water_metrics.get("mean_resistance_proxy"),
            "mean_power_proxy_kw": calm_water_metrics.get("mean_power_proxy_kw"),
            "mean_fuel_proxy_kgph": calm_water_metrics.get("mean_fuel_proxy_kgph"),
            "aggregate_resistance_proxy": calm_water_metrics.get("aggregate_resistance_proxy"),
            "aggregate_power_proxy_kw": calm_water_metrics.get("aggregate_power_proxy_kw"),
            "aggregate_fuel_proxy_kgph": calm_water_metrics.get("aggregate_fuel_proxy_kgph"),
            "reference_aggregate_resistance_proxy": calm_water_metrics.get("reference_aggregate_resistance_proxy"),
            "reference_aggregate_power_proxy_kw": calm_water_metrics.get("reference_aggregate_power_proxy_kw"),
            "reference_aggregate_fuel_proxy_kgph": calm_water_metrics.get("reference_aggregate_fuel_proxy_kgph"),
            "resistance_improvement_pct": calm_water_metrics.get("resistance_improvement_pct"),
            "power_improvement_pct": calm_water_metrics.get("power_improvement_pct"),
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
