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
        geometry.prepare_geometry(case_dir, Path(command.source_path))
        candidates = geometry.generate_candidates(case_dir, count=command.candidate_count)
        repository.save_candidate_index(case.case_id, candidates)

        evaluated_candidates = evaluation.evaluate_candidates(candidates)
        json_store.write(case_dir / "evaluation_index.json", evaluated_candidates)
        best_candidate = optimization.choose_best(evaluated_candidates)
        case.status = CaseStatus.ASSEMBLING_RESULTS
        repository.save_case(case)
        report.build_html_report(
            case_dir,
            {
                "case_name": case.case_name,
                "status": CaseStatus.COMPLETED.value,
                "best_candidate_id": best_candidate["candidate_id"],
                "best_candidate": best_candidate,
                "ranked_candidates": sorted(
                    evaluated_candidates,
                    key=lambda item: item["mid_score"],
                ),
                "runtime_budget_hours": command.runtime_budget_hours,
                "candidate_count": command.candidate_count,
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
