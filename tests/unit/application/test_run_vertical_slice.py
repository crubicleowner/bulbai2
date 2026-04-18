import json
from pathlib import Path

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.application.use_cases.run_vertical_slice import run_vertical_slice


def test_run_vertical_slice_creates_case_candidates_and_report(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    source_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="dtmb-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    candidate_index = json.loads((case_dir / "candidate_index.json").read_text(encoding="utf-8"))
    report_path = case_dir / "outputs" / "reports" / "report.html"
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))

    assert summary.case_name == "dtmb-demo"
    assert summary.status == "completed"
    assert summary.best_candidate_id == "candidate-3"
    assert case_payload["status"] == "imported"
    assert len(candidate_index) == 3
    assert report_path.exists()
    assert "candidate-3" in report_path.read_text(encoding="utf-8")
