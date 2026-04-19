from pathlib import Path

import pytest
import trimesh

from bulbopt.app.bootstrap import bootstrap_application
from bulbopt.domain.core.models import OptimizationCase
from bulbopt.infrastructure.adapters.html_report import HtmlReportAdapter
from bulbopt.storage.filesystem.json_store import JsonStore
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def _write_valid_stl(path: Path) -> None:
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    path.write_bytes(trimesh.exchange.stl.export_stl(mesh))


def test_bootstrap_application_runs_vertical_slice_and_writes_report(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    project_root = tmp_path / "projects"
    app = bootstrap_application(project_root=project_root)

    assert app["settings"].project_root == project_root
    assert app["settings"].openfoam_available is False
    assert app["settings"].default_candidate_count == 3

    summary = app["run_vertical_slice"](
        case_name="demo-case",
        source_path=str(source_path),
        vessel_length_m=142.0,
        vessel_beam_m=19.1,
        vessel_draft_m=6.0,
        displacement_t=8420.0,
        speed_knots=[18.0, 20.0],
    )

    case_dirs = list(project_root.iterdir())
    case_payload = JsonStore().read(case_dirs[0] / "case.json")
    report_html = (case_dirs[0] / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert summary.status == "completed"
    assert len(case_dirs) == 1
    assert (case_dirs[0] / "outputs" / "reports" / "report.html").exists()
    assert case_payload["status"] == "completed"
    assert case_payload["is_recoverable"] is False
    assert "Resistance proxy" in report_html
    assert "Slenderness ratio" in report_html
    assert summary.best_candidate_id in report_html
    assert "Processed candidates: 3" in report_html
    assert "Candidate Comparison" in report_html
    assert "candidate-1" in report_html
    assert "candidate-2" in report_html
    assert "candidate-3" in report_html


def test_repository_create_case_rolls_back_when_initial_write_fails(tmp_path: Path) -> None:
    class FailingJsonStore(JsonStore):
        def write(self, path: Path, payload: object) -> None:
            if path.name == "metadata.json":
                raise OSError("simulated write failure")
            super().write(path, payload)

    repository = FilesystemProjectRepository(
        root_dir=tmp_path / "projects",
        json_store=FailingJsonStore(),
    )
    case = OptimizationCase.new(case_id="case-rollback", case_name="rollback-demo")

    with pytest.raises(OSError, match="simulated write failure"):
        repository.create_case(case)

    assert repository.case_dir(case.case_id).exists() is False



def test_vertical_slice_builds_report_from_persisted_assembling_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)
    project_root = tmp_path / "projects"
    app = bootstrap_application(project_root=project_root)
    captured_statuses: dict[str, str] = {}
    original_build_html_report = HtmlReportAdapter.build_html_report

    def capture_report_context(self: HtmlReportAdapter, case_dir: Path, context: dict) -> Path:
        case_payload = JsonStore().read(case_dir / "case.json")
        captured_statuses["persisted_status"] = case_payload["status"]
        captured_statuses["report_status"] = context["status"]
        return original_build_html_report(self, case_dir, context)

    monkeypatch.setattr(HtmlReportAdapter, "build_html_report", capture_report_context)

    app["run_vertical_slice"](
        case_name="demo-case",
        source_path=str(source_path),
        vessel_length_m=142.0,
        vessel_beam_m=19.1,
        vessel_draft_m=6.0,
        displacement_t=8420.0,
        speed_knots=[18.0, 20.0],
    )

    assert captured_statuses["persisted_status"] == "assembling_results"
    assert captured_statuses["report_status"] == "completed"
