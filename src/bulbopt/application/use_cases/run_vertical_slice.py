from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from bulbopt.application.contracts.models import CaseSummary, CreateCaseCommand
from bulbopt.domain.core.models import CaseStatus, OptimizationCase
from bulbopt.infrastructure.adapters.html_report import HtmlReportAdapter
from bulbopt.infrastructure.adapters.stub_evaluation import StubEvaluationAdapter
from bulbopt.infrastructure.adapters.stub_geometry import StubGeometryAdapter
from bulbopt.infrastructure.adapters.stub_optimization import StubOptimizationAdapter
from bulbopt.storage.filesystem.json_store import JsonStore
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def run_vertical_slice(project_root: Path, command: CreateCaseCommand) -> CaseSummary:
    repository = FilesystemProjectRepository(root_dir=project_root)
    json_store = JsonStore()
    case = OptimizationCase.new(case_id=f"case-{uuid4().hex[:8]}", case_name=command.case_name)
    case.source_path = command.source_path
    case.status = CaseStatus.IMPORTED
    case_dir = repository.create_case(case)

    geometry = StubGeometryAdapter()
    evaluation = StubEvaluationAdapter()
    optimization = StubOptimizationAdapter()
    report = HtmlReportAdapter(template_root=_template_root())

    geometry.prepare_geometry(case_dir, Path(command.source_path))
    candidates = geometry.generate_candidates(case_dir, count=3)
    repository.save_candidate_index(case.case_id, candidates)

    evaluated_candidates = evaluation.evaluate_candidates(candidates)
    json_store.write(case_dir / "evaluation_index.json", evaluated_candidates)
    best_candidate = optimization.choose_best(evaluated_candidates)
    report.build_html_report(
        case_dir,
        {
            "case_name": case.case_name,
            "status": "completed",
            "best_candidate_id": best_candidate["candidate_id"],
            "openfoam_available": False,
            "high_fidelity_used": False,
        },
    )

    return CaseSummary(
        case_id=case.case_id,
        case_name=case.case_name,
        status="completed",
        best_candidate_id=best_candidate["candidate_id"],
    )


def _template_root() -> Path:
    return Path(__file__).resolve().parents[2] / "reporting" / "templates"
