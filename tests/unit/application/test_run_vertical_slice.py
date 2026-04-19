import json
from pathlib import Path

import pytest
import trimesh

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.application.use_cases import run_vertical_slice as run_vertical_slice_module
from bulbopt.application.use_cases.run_vertical_slice import run_vertical_slice


def _write_valid_stl(path: Path) -> bytes:
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    stl_bytes = trimesh.exchange.stl.export_stl(mesh)
    path.write_bytes(stl_bytes)
    return stl_bytes


def test_run_vertical_slice_creates_case_candidates_and_report(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

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
    evaluation_index = json.loads((case_dir / "evaluation_index.json").read_text(encoding="utf-8"))
    optimization_summary = json.loads(
        (case_dir / "working" / "evaluation" / "optimization_summary.json").read_text(encoding="utf-8")
    )
    geometry_analysis = json.loads(
        (case_dir / "working" / "repaired" / "geometry_analysis.json").read_text(encoding="utf-8")
    )
    artifacts_index = json.loads((case_dir / "artifacts_index.json").read_text(encoding="utf-8"))
    report_path = case_dir / "outputs" / "reports" / "report.html"
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    metadata_payload = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))

    assert summary.case_name == "dtmb-demo"
    assert summary.status == "completed"
    assert summary.best_candidate_id == "candidate-3"
    assert case_payload["status"] == "completed"
    assert case_payload["is_recoverable"] is False
    assert case_payload["summary_metrics"]["geometry"]["vertices_count"] > 0
    assert case_payload["summary_metrics"]["evaluation"]["best_candidate_id"] == "candidate-3"
    assert case_payload["summary_metrics"]["evaluation"]["best_candidate_geometry_path"].endswith("candidate-3.stl")
    assert case_payload["summary_metrics"]["hydrostatics"]["volume_delta_pct"] >= 0.0
    assert "draft_delta_m" in case_payload["summary_metrics"]["hydrostatics"]
    assert "hydrostatic_penalty" in case_payload["summary_metrics"]["hydrostatics"]
    assert case_payload["summary_metrics"]["hydrostatics"]["constraint_status"] in {"ok", "warn"}
    assert isinstance(case_payload["summary_metrics"]["hydrostatics"]["warnings"], list)
    assert case_payload["summary_metrics"]["execution"]["processed_candidates"] == 3
    assert case_payload["summary_metrics"]["optimization"]["ranked_count"] == 3
    assert len(case_payload["summary_metrics"]["candidates"]["rows"]) == 3
    assert metadata_payload["create_case_command"]["candidate_count"] == 3
    assert metadata_payload["create_case_command"]["speed_knots"] == [18.0, 20.0]
    assert metadata_payload["create_case_command"]["runtime_budget_hours"] == 8
    assert len(candidate_index) == 3
    assert len(evaluation_index) == 3
    assert optimization_summary["ranked_count"] == 3
    assert optimization_summary["best_candidate_id"] == "candidate-3"
    assert optimization_summary["mid_score_spread"] > 0.0
    assert artifacts_index["best_candidate_stl"].endswith("candidate-3.stl")
    assert geometry_analysis["quality_report"]["vertices_count"] > 0
    assert geometry_analysis["quality_report"]["faces_count"] > 0
    assert geometry_analysis["quality_report"]["primary_axis"] == 0
    assert geometry_analysis["bulb_region"]["axis_max"] > geometry_analysis["bulb_region"]["axis_min"]
    assert (case_dir / "working" / "repaired" / "repaired.stl").exists()
    assert evaluation_index[0]["geometry_metrics"]["axial_extent_m"] > 0.0
    assert evaluation_index[0]["geometry_metrics"]["beam_extent_m"] > 0.0
    assert evaluation_index[0]["geometry_metrics"]["draft_extent_m"] > 0.0
    assert evaluation_index[0]["geometry_metrics"]["slenderness_ratio"] > 0.0
    assert evaluation_index[0]["geometry_metrics"]["surface_area_m2"] > 0.0
    assert evaluation_index[0]["hydrostatics_metrics"]["volume_proxy_m3"] > 0.0
    assert evaluation_index[0]["hydrostatics_metrics"]["volume_delta_pct"] >= 0.0
    assert evaluation_index[0]["hydrostatics_metrics"]["constraint_status"] in {"ok", "warn"}
    assert evaluation_index[0]["score_components"]["resistance_proxy"] > 0.0
    assert evaluation_index[0]["score_components"]["hydrostatic_penalty"] >= 0.0
    assert evaluation_index[2]["mid_score"] < evaluation_index[0]["mid_score"]
    assert report_path.exists()
    report_html = report_path.read_text(encoding="utf-8")
    assert "candidate-3" in report_html
    assert "Runtime budget" in report_html
    assert "Candidate count" in report_html
    assert "Optimization summary" in report_html
    assert "Ranked candidates: 3" in report_html
    assert "Hydrostatics-lite" in report_html
    assert "Hydrostatic penalty" in report_html
    assert "Constraint status" in report_html


def test_run_vertical_slice_fails_fast_when_no_candidates_are_evaluated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    def return_empty_results(self, candidates: list[dict], objective_weights: dict[str, float] | None = None) -> list[dict]:
        return []

    monkeypatch.setattr(
        run_vertical_slice_module.StubEvaluationAdapter,
        "evaluate_candidates",
        return_empty_results,
    )

    with pytest.raises(ValueError, match="No evaluated candidates available for selection"):
        run_vertical_slice(
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

    case_dirs = list((tmp_path / "projects").iterdir())
    assert len(case_dirs) == 1

    case_payload = json.loads((case_dirs[0] / "case.json").read_text(encoding="utf-8"))

    assert case_payload["status"] == "failed"
    assert case_payload["is_recoverable"] is True


def test_run_vertical_slice_preserves_binary_stl_input(tmp_path: Path) -> None:
    source_path = tmp_path / "binary-demo.stl"
    binary_stl = (
        (b"Binary STL demo" + b"\xff\xfe\xfa" + b"\x00" * 62)[:80]
        + (1).to_bytes(4, byteorder="little")
        + (b"\x80" * 50)
    )
    source_path.write_bytes(binary_stl)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="binary-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    repaired_path = tmp_path / "projects" / summary.case_id / "working" / "repaired" / "repaired.stl"

    assert repaired_path.read_bytes() == binary_stl


def test_run_vertical_slice_generates_distinct_candidate_meshes(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="candidate-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    repaired_path = case_dir / "working" / "repaired" / "repaired.stl"
    candidate_paths = [
        case_dir / "working" / "candidates" / "candidate-1.stl",
        case_dir / "working" / "candidates" / "candidate-2.stl",
        case_dir / "working" / "candidates" / "candidate-3.stl",
    ]

    repaired_bytes = repaired_path.read_bytes()
    candidate_bytes = [path.read_bytes() for path in candidate_paths]

    assert all(path.exists() for path in candidate_paths)
    assert all(data for data in candidate_bytes)
    assert any(data != repaired_bytes for data in candidate_bytes)
    assert len({data for data in candidate_bytes}) == 3


def test_run_vertical_slice_respects_requested_candidate_count(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="count-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
            candidate_count=5,
            runtime_budget_hours=12,
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    candidate_index = json.loads((case_dir / "candidate_index.json").read_text(encoding="utf-8"))
    evaluation_index = json.loads((case_dir / "evaluation_index.json").read_text(encoding="utf-8"))
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert len(candidate_index) == 5
    assert len(evaluation_index) == 5
    assert "Candidate count: 5" in report_html
    assert "Runtime budget: 12 h" in report_html


def test_run_vertical_slice_applies_custom_objective_weights(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    default_summary = run_vertical_slice(
        project_root=tmp_path / "projects-default",
        command=CreateCaseCommand(
            case_name="weights-default",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )
    weighted_summary = run_vertical_slice(
        project_root=tmp_path / "projects-weighted",
        command=CreateCaseCommand(
            case_name="weights-custom",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
            resistance_weight=1.4,
            axial_gain_weight=0.2,
            draft_reduction_weight=0.0,
            beam_growth_weight=0.2,
        ),
    )

    default_case_dir = tmp_path / "projects-default" / default_summary.case_id
    weighted_case_dir = tmp_path / "projects-weighted" / weighted_summary.case_id
    default_eval = json.loads((default_case_dir / "evaluation_index.json").read_text(encoding="utf-8"))
    weighted_eval = json.loads((weighted_case_dir / "evaluation_index.json").read_text(encoding="utf-8"))
    weighted_metadata = json.loads((weighted_case_dir / "metadata.json").read_text(encoding="utf-8"))
    weighted_report = (weighted_case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert weighted_metadata["create_case_command"]["resistance_weight"] == 1.4
    assert weighted_metadata["create_case_command"]["axial_gain_weight"] == 0.2
    assert weighted_eval[0]["mid_score"] != default_eval[0]["mid_score"]
    assert "Objective weights" in weighted_report
    assert "Resistance weight: 1.4" in weighted_report


def test_run_vertical_slice_marks_case_failed_when_source_stl_is_missing(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing.stl"
    project_root = tmp_path / "projects"

    with pytest.raises(FileNotFoundError):
        run_vertical_slice(
            project_root=project_root,
            command=CreateCaseCommand(
                case_name="missing-demo",
                source_path=str(missing_path),
                vessel_length_m=142.0,
                vessel_beam_m=19.1,
                vessel_draft_m=6.0,
                displacement_t=8420.0,
                speed_knots=[18.0, 20.0],
            ),
        )

    case_dirs = list(project_root.iterdir())
    assert len(case_dirs) == 1

    case_payload = json.loads((case_dirs[0] / "case.json").read_text(encoding="utf-8"))

    assert case_payload["status"] == "failed"
    assert case_payload["is_recoverable"] is True


def test_run_vertical_slice_marks_case_failed_when_source_stl_is_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)
    project_root = tmp_path / "projects"
    original_read_bytes = Path.read_bytes

    def raise_os_error(self: Path) -> bytes:
        if self == source_path:
            raise OSError("simulated unreadable STL")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", raise_os_error)

    with pytest.raises(OSError, match="simulated unreadable STL"):
        run_vertical_slice(
            project_root=project_root,
            command=CreateCaseCommand(
                case_name="unreadable-demo",
                source_path=str(source_path),
                vessel_length_m=142.0,
                vessel_beam_m=19.1,
                vessel_draft_m=6.0,
                displacement_t=8420.0,
                speed_knots=[18.0, 20.0],
            ),
        )

    case_dirs = list(project_root.iterdir())
    assert len(case_dirs) == 1

    case_payload = json.loads((case_dirs[0] / "case.json").read_text(encoding="utf-8"))

    assert case_payload["status"] == "failed"
    assert case_payload["is_recoverable"] is True
