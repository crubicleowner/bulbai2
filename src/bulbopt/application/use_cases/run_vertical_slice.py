from __future__ import annotations

from pathlib import Path

from bulbopt.application.contracts.models import CaseSummary, CreateCaseCommand
from bulbopt.application.use_cases.create_case import create_case
from bulbopt.domain.core.models import CaseStatus
from bulbopt.infrastructure.adapters.html_report import HtmlReportAdapter
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
        }
        evaluated_candidates = evaluation.evaluate_candidates(candidates, objective_weights=objective_weights)
        json_store.write(case_dir / "evaluation_index.json", evaluated_candidates)
        ranked_candidates = optimization.rank_candidates(evaluated_candidates)
        best_candidate = ranked_candidates[0]
        optimization_summary = optimization.summarize_ranking(evaluated_candidates)
        optimization_summary_path = case_dir / "working" / "evaluation" / "optimization_summary.json"
        json_store.write(optimization_summary_path, optimization_summary)
        artifacts_index_path = case_dir / "artifacts_index.json"
        artifacts_index = json_store.read(artifacts_index_path)
        artifacts_index["optimization_summary"] = str(optimization_summary_path)
        json_store.write(artifacts_index_path, artifacts_index)
        case.summary_metrics = _build_case_summary_metrics(
            geometry_analysis=geometry_analysis,
            best_candidate=best_candidate,
            optimization_summary=optimization_summary,
            runtime_budget_hours=command.runtime_budget_hours,
            candidate_count=command.candidate_count,
            objective_weights=objective_weights,
            ranked_candidates=ranked_candidates,
        )
        case.status = CaseStatus.ASSEMBLING_RESULTS
        repository.save_case(case)
        report.build_html_report(
            case_dir,
            {
                "case_name": case.case_name,
                "status": CaseStatus.COMPLETED.value,
                "best_candidate_id": best_candidate["candidate_id"],
                "best_candidate": best_candidate,
                "ranked_candidates": ranked_candidates,
                "optimization_summary": optimization_summary,
                "runtime_budget_hours": command.runtime_budget_hours,
                "candidate_count": command.candidate_count,
                "processed_candidates": len(evaluated_candidates),
                "objective_weights": objective_weights,
                "openfoam_available": False,
                "high_fidelity_used": False,
            },
        )
        case.status = CaseStatus.COMPLETED
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


def _build_case_summary_metrics(
    geometry_analysis: dict,
    best_candidate: dict,
    optimization_summary: dict,
    runtime_budget_hours: int,
    candidate_count: int,
    objective_weights: dict[str, float],
    ranked_candidates: list[dict],
) -> dict:
    quality_report = geometry_analysis.get("quality_report", {})
    geometry_metrics = best_candidate.get("geometry_metrics", {})
    score_components = best_candidate.get("score_components", {})
    candidate_rows = [
        (
            f"{item.get('candidate_id', 'n/a')} | "
            f"fast={item.get('fast_score', 'n/a')} | "
            f"mid={item.get('mid_score', 'n/a')}"
        )
        for item in ranked_candidates
    ]
    candidate_summary = "Candidates summary: not available"
    if ranked_candidates:
        candidate_summary = "Candidates: " + " | ".join(
            f"{item.get('candidate_id', 'n/a')} mid={item.get('mid_score', 'n/a')}"
            for item in ranked_candidates
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
            "fast_score": best_candidate.get("fast_score"),
            "mid_score": best_candidate.get("mid_score"),
            "resistance_proxy": score_components.get("resistance_proxy"),
        },
        "execution": {
            "runtime_budget_hours": runtime_budget_hours,
            "candidate_count": candidate_count,
            "processed_candidates": len(ranked_candidates),
        },
        "objective_weights": objective_weights,
        "optimization": optimization_summary,
        "candidates": {
            "summary": candidate_summary,
            "rows": candidate_rows,
        },
    }
