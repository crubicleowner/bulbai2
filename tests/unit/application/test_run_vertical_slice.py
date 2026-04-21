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
    assert case_payload["summary_metrics"]["calm_water"]["speed_count"] == 2
    assert case_payload["summary_metrics"]["calm_water"]["mean_power_proxy_kw"] > 0.0
    assert case_payload["summary_metrics"]["calm_water"]["aggregate_power_proxy_kw"] > 0.0
    assert case_payload["summary_metrics"]["calm_water"]["mean_fuel_proxy_kgph"] > 0.0
    assert case_payload["summary_metrics"]["calm_water"]["aggregate_fuel_proxy_kgph"] > 0.0
    assert case_payload["summary_metrics"]["calm_water"]["surrogate_model"] == "enhanced_geometry_v1"
    assert case_payload["summary_metrics"]["calm_water"]["mean_froude_number"] > 0.0
    assert case_payload["summary_metrics"]["calm_water"]["mean_effective_power_proxy_kw"] > 0.0
    assert "effective_power_improvement_pct" in case_payload["summary_metrics"]["calm_water"]
    assert case_payload["summary_metrics"]["calm_water"]["aggregate_resistance_proxy"] > 0.0
    assert case_payload["summary_metrics"]["calm_water"]["reference_aggregate_fuel_proxy_kgph"] > 0.0
    assert "resistance_improvement_pct" in case_payload["summary_metrics"]["calm_water"]
    assert "power_improvement_pct" in case_payload["summary_metrics"]["calm_water"]
    assert "fuel_improvement_pct" in case_payload["summary_metrics"]["calm_water"]
    assert (
        case_payload["summary_metrics"]["calm_water"]["fuel_improvement_pct"]
        != case_payload["summary_metrics"]["calm_water"]["power_improvement_pct"]
    )
    assert case_payload["summary_metrics"]["calm_water"]["dominant_speed_knots"] == 20.0
    assert case_payload["summary_metrics"]["hydrostatics"]["volume_delta_pct"] >= 0.0
    assert "draft_delta_m" in case_payload["summary_metrics"]["hydrostatics"]
    assert "hydrostatic_penalty" in case_payload["summary_metrics"]["hydrostatics"]
    assert case_payload["summary_metrics"]["hydrostatics"]["constraint_status"] in {"ok", "warn"}
    assert isinstance(case_payload["summary_metrics"]["hydrostatics"]["warnings"], list)
    assert case_payload["summary_metrics"]["execution"]["processed_candidates"] == 3
    assert case_payload["summary_metrics"]["optimization"]["ranked_count"] == 3
    assert case_payload["summary_metrics"]["optimization_trace"]["summary"].startswith("Optimization trace:")
    assert len(case_payload["summary_metrics"]["optimization_trace"]["rows"]) == 2
    assert len(case_payload["summary_metrics"]["candidates"]["rows"]) == 3
    assert case_payload["summary_metrics"]["high_fidelity_boundary"]["adapter"] == "openfoam"
    assert case_payload["summary_metrics"]["high_fidelity_boundary"]["available"] is False
    assert case_payload["summary_metrics"]["high_fidelity_boundary"]["used"] is False
    assert case_payload["summary_metrics"]["high_fidelity_boundary"]["case_built"] is True
    assert case_payload["summary_metrics"]["high_fidelity_boundary"]["case_directory"].endswith("working\\openfoam_case")
    assert case_payload["summary_metrics"]["high_fidelity_boundary"]["mesh_templates"] == [
        "blockMeshDict",
        "snappyHexMeshDict",
    ]
    assert case_payload["summary_metrics"]["high_fidelity_boundary"]["runner_status"] == "skipped"
    assert case_payload["summary_metrics"]["high_fidelity_boundary"]["runner_reason"] == "openfoam_unavailable"
    assert case_payload["summary_metrics"]["high_fidelity_boundary"]["runner_recoverable"] is True
    assert case_payload["summary_metrics"]["selection_priority"]["calibration_model"] == "multi_condition_v1"
    assert case_payload["summary_metrics"]["selection_priority"]["selection_priority_score"] > 0.0
    assert case_payload["summary_metrics"]["selection_priority"]["cfd_focus_band"] in {"screen", "review", "promote"}
    assert metadata_payload["create_case_command"]["candidate_count"] == 3
    assert metadata_payload["create_case_command"]["speed_knots"] == [18.0, 20.0]
    assert metadata_payload["create_case_command"]["operational_profile_weights"] is None
    assert metadata_payload["create_case_command"]["wave_scenario_heights_m"] is None
    assert metadata_payload["create_case_command"]["wave_scenario_periods_s"] is None
    assert metadata_payload["create_case_command"]["wave_scenario_weights"] is None
    assert metadata_payload["create_case_command"]["calm_water_condition_weight"] == 0.7
    assert metadata_payload["create_case_command"]["wave_condition_weight"] == 0.3
    assert metadata_payload["create_case_command"]["max_volume_delta_pct"] == 4.5
    assert metadata_payload["create_case_command"]["max_draft_delta_m"] == 0.05
    assert metadata_payload["create_case_command"]["max_speed_balance_ratio"] == 4.0
    assert metadata_payload["create_case_command"]["max_wave_penalty"] == 1.5
    assert metadata_payload["create_case_command"]["reject_volume_delta_pct"] == 9.0
    assert metadata_payload["create_case_command"]["reject_draft_delta_m"] == 0.1
    assert metadata_payload["create_case_command"]["reject_speed_balance_ratio"] == 8.0
    assert metadata_payload["create_case_command"]["reject_wave_penalty"] == 3.0
    assert metadata_payload["create_case_command"]["runtime_budget_hours"] == 8
    assert case_payload["summary_metrics"]["operational_profile"]["profile_source"] == "derived_from_speed_knots"
    assert case_payload["summary_metrics"]["operational_profile"]["dominant_speed_knots"] == 20.0
    assert case_payload["summary_metrics"]["acceptability_thresholds"]["max_volume_delta_pct"] == 4.5
    assert case_payload["summary_metrics"]["acceptability_thresholds"]["reject_volume_delta_pct"] == 9.0
    assert case_payload["summary_metrics"]["acceptability_thresholds"]["max_wave_penalty"] == 1.5
    assert case_payload["summary_metrics"]["acceptability_thresholds"]["reject_wave_penalty"] == 3.0
    assert case_payload["summary_metrics"]["acceptability"]["is_acceptable"] is True
    assert case_payload["summary_metrics"]["acceptability"]["level"] == "ok"
    assert case_payload["summary_metrics"]["acceptability"]["hydrostatics_status"] == "ok"
    assert case_payload["summary_metrics"]["acceptability"]["operational_profile_status"] == "ok"
    assert case_payload["summary_metrics"]["acceptability"]["wave_response_status"] == "ok"
    assert case_payload["summary_metrics"]["multi_condition_objective"]["combined_penalty"] >= 0.0
    assert case_payload["summary_metrics"]["multi_condition_objective"]["dominant_condition"] in {
        "calm_water",
        "wave_response",
    }
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
    assert len(evaluation_index[0]["calm_water_metrics"]["speed_points"]) == 2
    assert evaluation_index[0]["calm_water_metrics"]["speed_points"][0]["froude_number"] > 0.0
    assert evaluation_index[0]["calm_water_metrics"]["mean_power_proxy_kw"] > 0.0
    assert evaluation_index[0]["calm_water_metrics"]["mean_effective_power_proxy_kw"] > 0.0
    assert evaluation_index[0]["calm_water_metrics"]["aggregate_power_proxy_kw"] > 0.0
    assert evaluation_index[0]["calm_water_metrics"]["mean_fuel_proxy_kgph"] > 0.0
    assert evaluation_index[0]["calm_water_metrics"]["aggregate_fuel_proxy_kgph"] > 0.0
    assert "reference_aggregate_power_proxy_kw" in evaluation_index[0]["calm_water_metrics"]
    assert "reference_aggregate_fuel_proxy_kgph" in evaluation_index[0]["calm_water_metrics"]
    assert "fuel_improvement_pct" in evaluation_index[0]["calm_water_metrics"]
    assert (
        evaluation_index[0]["calm_water_metrics"]["fuel_improvement_pct"]
        != evaluation_index[0]["calm_water_metrics"]["power_improvement_pct"]
    )
    assert evaluation_index[0]["calm_water_metrics"]["dominant_speed_knots"] == 20.0
    assert sum(item["speed_weight"] for item in evaluation_index[0]["calm_water_metrics"]["speed_points"]) == pytest.approx(1.0)
    assert evaluation_index[0]["score_components"]["resistance_proxy"] > 0.0
    assert evaluation_index[0]["score_components"]["hydrostatic_penalty"] >= 0.0
    assert evaluation_index[0]["score_components"]["calm_water_penalty"] >= 0.0
    assert evaluation_index[0]["score_components"]["wave_penalty"] >= 0.0
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
    assert "Calm-water surrogate" in report_html
    assert "Mean power proxy" in report_html
    assert "Aggregate power proxy" in report_html
    assert "Effective power proxy" in report_html
    assert "Mean fuel proxy" in report_html
    assert "Aggregate fuel proxy" in report_html
    assert "Fuel improvement" in report_html
    assert "Baseline comparison" in report_html
    assert "Reference aggregate fuel proxy" in report_html
    assert "Reference vs candidate" in report_html
    assert "Dominant speed" in report_html
    assert "Acceptability summary" in report_html
    assert "Acceptability thresholds" in report_html
    assert "Acceptability level" in report_html
    assert "level=ok" in report_html
    assert "reasons=none" in report_html
    assert "resistance=" in report_html
    assert "hydro=" in report_html
    assert "calm=" in report_html
    assert "wave=" in report_html
    assert "Optimization trace" in report_html
    assert "High-fidelity boundary" in report_html
    assert "OpenFOAM case directory" in report_html
    assert "Surrogate model" in report_html
    assert "Selection priority" in report_html
    assert "Runner status" in report_html
    assert "vs" in case_payload["summary_metrics"]["optimization_trace"]["rows"][0]
    assert "hydro=" in case_payload["summary_metrics"]["optimization_trace"]["rows"][0]
    assert "wave=" in case_payload["summary_metrics"]["optimization_trace"]["rows"][0]


def test_run_vertical_slice_supports_weighted_wave_scenarios_and_boundary_summary(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="wave-scenarios",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[16.0, 20.0, 24.0],
            operational_profile_weights=[0.2, 0.3, 0.5],
            wave_scenario_heights_m=[1.0, 2.0],
            wave_scenario_periods_s=[6.0, 8.0],
            wave_scenario_weights=[0.25, 0.75],
            max_wave_penalty=20.0,
            reject_wave_penalty=40.0,
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    metadata_payload = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    wave_response = case_payload["summary_metrics"]["wave_response"]
    boundary = case_payload["summary_metrics"]["high_fidelity_boundary"]

    assert summary.status == "completed"
    assert wave_response["scenario_count"] == 2
    assert wave_response["scenario_source"] == "user_defined"
    assert wave_response["dominant_scenario_label"] == "2.0m@8.0s"
    assert len(wave_response["scenario_rows"]) == 2
    assert "2.0m@8.0s" in wave_response["scenario_rows"][1]
    assert boundary["adapter"] == "openfoam"
    assert boundary["mode"] == "optional"
    assert boundary["used"] is False
    assert metadata_payload["create_case_command"]["wave_scenario_heights_m"] == [1.0, 2.0]
    assert metadata_payload["create_case_command"]["wave_scenario_periods_s"] == [6.0, 8.0]
    assert metadata_payload["create_case_command"]["wave_scenario_weights"] == [0.25, 0.75]
    assert "Wave scenarios" in report_html
    assert "2.0m@8.0s" in report_html
    assert "High-fidelity boundary" in report_html


def test_run_vertical_slice_fails_fast_when_no_candidates_are_evaluated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    def return_empty_results(
        self,
        candidates: list[dict],
        objective_weights: dict[str, float] | None = None,
        speed_knots: list[float] | None = None,
        operational_profile_weights: list[float] | None = None,
        wave_height_m: float = 0.0,
        wave_period_s: float = 0.0,
        wave_scenario_heights_m: list[float] | None = None,
        wave_scenario_periods_s: list[float] | None = None,
        wave_scenario_weights: list[float] | None = None,
        acceptability_thresholds: dict[str, float] | None = None,
    ) -> list[dict]:
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


def test_run_vertical_slice_applies_user_defined_operational_profile_weights(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects-profile",
        command=CreateCaseCommand(
            case_name="profile-custom",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[16.0, 20.0, 24.0],
            operational_profile_weights=[0.2, 0.3, 0.5],
        ),
    )

    case_dir = tmp_path / "projects-profile" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    evaluation_index = json.loads((case_dir / "evaluation_index.json").read_text(encoding="utf-8"))
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert case_payload["summary_metrics"]["operational_profile"]["profile_source"] == "user_defined"
    assert case_payload["summary_metrics"]["operational_profile"]["speed_knots"] == [16.0, 20.0, 24.0]
    assert case_payload["summary_metrics"]["operational_profile"]["operational_profile_weights"] == [0.2, 0.3, 0.5]
    assert case_payload["summary_metrics"]["operational_profile"]["dominant_speed_knots"] == 24.0
    assert evaluation_index[0]["calm_water_metrics"]["speed_points"][0]["speed_weight"] == pytest.approx(0.2)
    assert evaluation_index[0]["calm_water_metrics"]["speed_points"][1]["speed_weight"] == pytest.approx(0.3)
    assert evaluation_index[0]["calm_water_metrics"]["speed_points"][2]["speed_weight"] == pytest.approx(0.5)
    assert evaluation_index[0]["calm_water_metrics"]["aggregate_fuel_proxy_kgph"] > 0.0
    assert "fuel_improvement_pct" in evaluation_index[0]["calm_water_metrics"]
    assert (
        evaluation_index[0]["calm_water_metrics"]["fuel_improvement_pct"]
        != evaluation_index[0]["calm_water_metrics"]["power_improvement_pct"]
    )
    assert "Operational profile" in report_html
    assert "Profile source: user_defined" in report_html


def test_run_vertical_slice_adds_wave_response_surrogate(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects-wave",
        command=CreateCaseCommand(
            case_name="wave-surrogate",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 22.0],
            wave_height_m=1.8,
            wave_period_s=7.5,
        ),
    )

    case_dir = tmp_path / "projects-wave" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    metadata_payload = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    evaluation_index = json.loads((case_dir / "evaluation_index.json").read_text(encoding="utf-8"))
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert case_payload["summary_metrics"]["wave_response"]["wave_height_m"] == 1.8
    assert case_payload["summary_metrics"]["wave_response"]["wave_period_s"] == 7.5
    assert case_payload["summary_metrics"]["wave_response"]["added_resistance_proxy"] > 0.0
    assert case_payload["summary_metrics"]["wave_response"]["added_power_proxy_kw"] > 0.0
    assert case_payload["summary_metrics"]["wave_response"]["wave_penalty"] > 0.0
    assert case_payload["summary_metrics"]["wave_response"]["condition_status"] == "active"
    assert case_payload["summary_metrics"]["multi_condition_objective"]["combined_penalty"] > 0.0
    assert case_payload["summary_metrics"]["multi_condition_objective"]["calm_water_weight"] == 0.7
    assert case_payload["summary_metrics"]["multi_condition_objective"]["wave_response_weight"] == 0.3
    assert evaluation_index[0]["wave_response_metrics"]["wave_height_m"] == 1.8
    assert evaluation_index[0]["wave_response_metrics"]["wave_period_s"] == 7.5
    assert evaluation_index[0]["wave_response_metrics"]["added_resistance_proxy"] > 0.0
    assert evaluation_index[0]["wave_response_metrics"]["added_power_proxy_kw"] > 0.0
    assert evaluation_index[0]["wave_response_metrics"]["wave_penalty"] > 0.0
    assert metadata_payload["create_case_command"]["wave_height_m"] == 1.8
    assert metadata_payload["create_case_command"]["wave_period_s"] == 7.5
    assert "Wave-response surrogate" in report_html
    assert "Added resistance proxy" in report_html
    assert "Wave penalty" in report_html
    assert "Multi-condition objective" in report_html
    assert "Combined penalty" in report_html


def test_run_vertical_slice_applies_wave_acceptability_thresholds(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects-wave-thresholds",
        command=CreateCaseCommand(
            case_name="wave-thresholds",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 22.0],
            wave_height_m=1.8,
            wave_period_s=7.5,
            max_wave_penalty=0.01,
            reject_wave_penalty=100.0,
        ),
    )

    case_dir = tmp_path / "projects-wave-thresholds" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert summary.status == "completed_with_warnings"
    assert case_payload["summary_metrics"]["acceptability"]["level"] == "warn"
    assert case_payload["summary_metrics"]["acceptability"]["wave_response_status"] == "warn"
    assert "wave_response_warn" in case_payload["summary_metrics"]["acceptability"]["reasons"]
    assert case_payload["summary_metrics"]["wave_response"]["wave_penalty"] > 0.01
    assert "Warn wave penalty" in report_html


def test_run_vertical_slice_builds_multi_condition_objective(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects-multi-condition",
        command=CreateCaseCommand(
            case_name="multi-condition",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[16.0, 20.0, 24.0],
            wave_height_m=1.8,
            wave_period_s=7.5,
            calm_water_condition_weight=0.55,
            wave_condition_weight=0.45,
        ),
    )

    case_dir = tmp_path / "projects-multi-condition" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert case_payload["summary_metrics"]["multi_condition_objective"]["calm_water_weight"] == 0.55
    assert case_payload["summary_metrics"]["multi_condition_objective"]["wave_response_weight"] == 0.45
    assert case_payload["summary_metrics"]["multi_condition_objective"]["combined_penalty"] > 0.0
    assert case_payload["summary_metrics"]["multi_condition_objective"]["combined_objective_score"] > 0.0
    assert case_payload["summary_metrics"]["multi_condition_objective"]["dominant_condition"] in {
        "calm_water",
        "wave_response",
    }
    assert "Multi-condition objective" in report_html
    assert "Dominant condition" in report_html


def test_run_vertical_slice_prefers_acceptable_candidate_over_better_penalized_score(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    def return_mixed_acceptability_results(
        self,
        candidates: list[dict],
        objective_weights: dict[str, float] | None = None,
        speed_knots: list[float] | None = None,
        operational_profile_weights: list[float] | None = None,
        wave_height_m: float = 0.0,
        wave_period_s: float = 0.0,
        wave_scenario_heights_m: list[float] | None = None,
        wave_scenario_periods_s: list[float] | None = None,
        wave_scenario_weights: list[float] | None = None,
        acceptability_thresholds: dict[str, float] | None = None,
    ) -> list[dict]:
        return [
            {
                **candidates[0],
                "status": "mid_score_ready",
                "fast_score": 1.1,
                "mid_score": 0.4,
                "objective_weights": objective_weights or {},
                "geometry_metrics": {"slenderness_ratio": 2.7},
                "hydrostatics_metrics": {"constraint_status": "warn", "warnings": ["volume_delta_exceeds_limit"]},
                "calm_water_metrics": {"profile_source": "user_defined", "dominant_speed_knots": 24.0},
                    "acceptability": {
                        "is_acceptable": False,
                        "level": "reject",
                        "hydrostatics_status": "warn",
                        "operational_profile_status": "ok",
                        "reasons": ["hydrostatics_warn"],
                },
                "score_components": {
                    "resistance_proxy": 0.4,
                    "hydrostatic_penalty": 0.58,
                    "calm_water_penalty": 0.3,
                },
            },
            {
                **candidates[1],
                "status": "mid_score_ready",
                "fast_score": 1.0,
                "mid_score": 0.6,
                "objective_weights": objective_weights or {},
                "geometry_metrics": {"slenderness_ratio": 2.6},
                "hydrostatics_metrics": {"constraint_status": "ok", "warnings": []},
                "calm_water_metrics": {"profile_source": "user_defined", "dominant_speed_knots": 24.0},
                    "acceptability": {
                        "is_acceptable": True,
                        "level": "ok",
                        "hydrostatics_status": "ok",
                        "operational_profile_status": "ok",
                        "reasons": [],
                },
                "score_components": {
                    "resistance_proxy": 0.45,
                    "hydrostatic_penalty": 0.1,
                    "calm_water_penalty": 0.2,
                },
            },
        ]

    monkeypatch.setattr(
        run_vertical_slice_module.StubEvaluationAdapter,
        "evaluate_candidates",
        return_mixed_acceptability_results,
    )

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="acceptability-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    optimization_summary = json.loads(
        (case_dir / "working" / "evaluation" / "optimization_summary.json").read_text(encoding="utf-8")
    )
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    candidates_id = "candidate-2"
    assert summary.best_candidate_id == candidates_id
    assert case_payload["summary_metrics"]["acceptability"]["is_acceptable"] is True
    assert case_payload["summary_metrics"]["acceptability"]["level"] == "ok"
    assert "candidate-1" in case_payload["summary_metrics"]["rejected_candidates"]["summary"]
    assert "hydrostatics_warn" in case_payload["summary_metrics"]["rejected_candidates"]["rows"][0]
    assert "candidate-2 over candidate-1" in case_payload["summary_metrics"]["optimization_trace"]["rows"][0]
    assert "ok beats reject" in case_payload["summary_metrics"]["optimization_trace"]["rows"][0]
    assert "hydro=0.1 vs 0.58" in case_payload["summary_metrics"]["optimization_trace"]["rows"][0]
    assert optimization_summary["best_candidate_id"] == candidates_id
    assert optimization_summary["acceptable_count"] == 1
    assert optimization_summary["unacceptable_count"] == 1
    assert optimization_summary["ok_count"] == 1
    assert optimization_summary["warn_count"] == 0
    assert optimization_summary["reject_count"] == 1
    assert "Rejected candidates" in report_html
    assert "candidate-1" in report_html
    assert "hydrostatics_warn" in report_html
    assert "resistance=" in report_html
    assert "Optimization trace" in report_html
    assert "hydro=0.1 vs 0.58" in report_html


def test_run_vertical_slice_prefers_warn_candidate_over_reject_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    def return_warn_and_reject_results(
        self,
        candidates: list[dict],
        objective_weights: dict[str, float] | None = None,
        speed_knots: list[float] | None = None,
        operational_profile_weights: list[float] | None = None,
        wave_height_m: float = 0.0,
        wave_period_s: float = 0.0,
        wave_scenario_heights_m: list[float] | None = None,
        wave_scenario_periods_s: list[float] | None = None,
        wave_scenario_weights: list[float] | None = None,
        acceptability_thresholds: dict[str, float] | None = None,
    ) -> list[dict]:
        return [
            {
                **candidates[0],
                "status": "mid_score_ready",
                "fast_score": 1.2,
                "mid_score": 0.3,
                "objective_weights": objective_weights or {},
                "geometry_metrics": {"slenderness_ratio": 2.7},
                "hydrostatics_metrics": {"constraint_status": "warn", "warnings": ["volume_delta_exceeds_limit"]},
                "calm_water_metrics": {"profile_source": "user_defined", "dominant_speed_knots": 24.0},
                "acceptability": {
                    "is_acceptable": False,
                    "level": "reject",
                    "hydrostatics_status": "reject",
                    "operational_profile_status": "ok",
                    "reasons": ["hydrostatics_reject"],
                },
                "score_components": {
                    "resistance_proxy": 0.3,
                    "hydrostatic_penalty": 0.9,
                    "calm_water_penalty": 0.3,
                },
            },
            {
                **candidates[1],
                "status": "mid_score_ready",
                "fast_score": 1.0,
                "mid_score": 0.6,
                "objective_weights": objective_weights or {},
                "geometry_metrics": {"slenderness_ratio": 2.6},
                "hydrostatics_metrics": {"constraint_status": "warn", "warnings": ["draft_delta_exceeds_limit"]},
                "calm_water_metrics": {"profile_source": "user_defined", "dominant_speed_knots": 24.0},
                "acceptability": {
                    "is_acceptable": True,
                    "level": "warn",
                    "hydrostatics_status": "warn",
                    "operational_profile_status": "ok",
                    "reasons": ["hydrostatics_warn"],
                },
                "score_components": {
                    "resistance_proxy": 0.45,
                    "hydrostatic_penalty": 0.2,
                    "calm_water_penalty": 0.2,
                },
            },
        ]

    monkeypatch.setattr(
        run_vertical_slice_module.StubEvaluationAdapter,
        "evaluate_candidates",
        return_warn_and_reject_results,
    )

    summary = run_vertical_slice(
        project_root=tmp_path / "projects-warn-vs-reject",
        command=CreateCaseCommand(
            case_name="warn-vs-reject-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    case_dir = tmp_path / "projects-warn-vs-reject" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    optimization_summary = json.loads(
        (case_dir / "working" / "evaluation" / "optimization_summary.json").read_text(encoding="utf-8")
    )

    assert summary.best_candidate_id == "candidate-2"
    assert summary.status == "completed_with_warnings"
    assert case_payload["summary_metrics"]["acceptability"]["level"] == "warn"
    assert "candidate-1" in case_payload["summary_metrics"]["rejected_candidates"]["summary"]
    assert optimization_summary["warn_count"] == 1
    assert optimization_summary["reject_count"] == 1
    assert "reasons=" in (
        case_dir / "outputs" / "reports" / "report.html"
    ).read_text(encoding="utf-8")


def test_run_vertical_slice_applies_custom_acceptability_thresholds(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects-strict-thresholds",
        command=CreateCaseCommand(
            case_name="strict-thresholds-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
            max_volume_delta_pct=0.1,
            max_draft_delta_m=0.001,
            max_speed_balance_ratio=1.1,
            reject_volume_delta_pct=0.2,
            reject_draft_delta_m=0.002,
            reject_speed_balance_ratio=2.2,
        ),
    )

    case_dir = tmp_path / "projects-strict-thresholds" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert summary.status == "completed_with_warnings"
    assert case_payload["summary_metrics"]["acceptability_thresholds"]["max_volume_delta_pct"] == 0.1
    assert case_payload["summary_metrics"]["acceptability"]["is_acceptable"] is False
    assert case_payload["summary_metrics"]["acceptability"]["level"] == "reject"
    assert "hydrostatics_warn" in case_payload["summary_metrics"]["acceptability"]["reasons"]
    assert "Acceptability thresholds" in report_html
    assert "Max volume delta: 0.1" in report_html


def test_run_vertical_slice_supports_separate_warn_and_reject_thresholds(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects-separated-thresholds",
        command=CreateCaseCommand(
            case_name="separated-thresholds-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
            max_volume_delta_pct=0.1,
            reject_volume_delta_pct=10.0,
            max_draft_delta_m=0.001,
            reject_draft_delta_m=1.0,
            max_speed_balance_ratio=1.1,
            reject_speed_balance_ratio=10.0,
        ),
    )

    case_dir = tmp_path / "projects-separated-thresholds" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert summary.status == "completed_with_warnings"
    assert case_payload["summary_metrics"]["acceptability"]["is_acceptable"] is True
    assert case_payload["summary_metrics"]["acceptability"]["level"] == "warn"
    assert case_payload["summary_metrics"]["acceptability_thresholds"]["reject_volume_delta_pct"] == 10.0
    assert case_payload["summary_metrics"]["acceptability_thresholds"]["reject_draft_delta_m"] == 1.0
    assert case_payload["summary_metrics"]["acceptability_thresholds"]["reject_speed_balance_ratio"] == 10.0
    assert "Reject volume delta" in report_html


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


def test_run_vertical_slice_marks_case_completed_with_warnings_when_best_candidate_warns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    def return_warning_results(
        self,
        candidates: list[dict],
        objective_weights: dict[str, float] | None = None,
        speed_knots: list[float] | None = None,
        operational_profile_weights: list[float] | None = None,
        wave_height_m: float = 0.0,
        wave_period_s: float = 0.0,
        wave_scenario_heights_m: list[float] | None = None,
        wave_scenario_periods_s: list[float] | None = None,
        wave_scenario_weights: list[float] | None = None,
        acceptability_thresholds: dict[str, float] | None = None,
    ) -> list[dict]:
        return [
            {
                **candidates[0],
                "status": "mid_score_ready",
                "fast_score": 1.0,
                "mid_score": 0.5,
                "objective_weights": objective_weights or {},
                "geometry_metrics": {
                    "axial_extent_m": 4.0,
                    "beam_extent_m": 1.5,
                    "draft_extent_m": 1.0,
                    "surface_area_m2": 20.0,
                    "slenderness_ratio": 2.6,
                    "nose_area_proxy_m2": 1.2,
                    "axial_gain_m": 0.1,
                    "beam_growth_m": 0.0,
                    "draft_reduction_m": 0.0,
                },
                "hydrostatics_metrics": {
                    "volume_proxy_m3": 6.0,
                    "reference_volume_proxy_m3": 5.0,
                    "volume_delta_pct": 5.0,
                    "draft_delta_m": 0.08,
                    "hydrostatic_penalty": 0.58,
                    "constraint_status": "warn",
                    "warnings": ["volume_delta_exceeds_limit", "draft_delta_exceeds_limit"],
                },
                "acceptability": {
                    "is_acceptable": True,
                    "level": "warn",
                    "hydrostatics_status": "warn",
                    "operational_profile_status": "ok",
                    "reasons": ["hydrostatics_warn"],
                },
                "score_components": {
                    "frontal_area_proxy_m2": 1.5,
                    "resistance_proxy": 0.4,
                    "hydrostatic_penalty": 0.58,
                },
            },
            {
                **candidates[1],
                "status": "mid_score_ready",
                "fast_score": 0.9,
                "mid_score": 1.2,
                "objective_weights": objective_weights or {},
                "geometry_metrics": {
                    "axial_extent_m": 3.9,
                    "beam_extent_m": 1.5,
                    "draft_extent_m": 1.0,
                    "surface_area_m2": 19.5,
                    "slenderness_ratio": 2.5,
                    "nose_area_proxy_m2": 1.1,
                    "axial_gain_m": 0.05,
                    "beam_growth_m": 0.0,
                    "draft_reduction_m": 0.0,
                },
                "hydrostatics_metrics": {
                    "volume_proxy_m3": 5.05,
                    "reference_volume_proxy_m3": 5.0,
                    "volume_delta_pct": 1.0,
                    "draft_delta_m": 0.01,
                    "hydrostatic_penalty": 0.11,
                    "constraint_status": "ok",
                    "warnings": [],
                },
                "acceptability": {
                    "is_acceptable": False,
                    "level": "reject",
                    "hydrostatics_status": "reject",
                    "operational_profile_status": "ok",
                    "reasons": ["operational_profile_warn"],
                },
                "score_components": {
                    "frontal_area_proxy_m2": 1.5,
                    "resistance_proxy": 0.45,
                    "hydrostatic_penalty": 0.11,
                },
            },
        ]

    monkeypatch.setattr(
        run_vertical_slice_module.StubEvaluationAdapter,
        "evaluate_candidates",
        return_warning_results,
    )

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="warning-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")

    assert summary.status == "completed_with_warnings"
    assert case_payload["status"] == "completed_with_warnings"
    assert case_payload["is_recoverable"] is False
    assert case_payload["summary_metrics"]["hydrostatics"]["constraint_status"] == "warn"
    assert "volume_delta_exceeds_limit" in case_payload["summary_metrics"]["hydrostatics"]["warnings"]
    assert "completed_with_warnings" in report_html


def test_run_vertical_slice_surfaces_repair_summary_in_html_report(tmp_path: Path) -> None:
    """Spec §14 demands engineering-honest reporting of repair activity so
    the HTML report always includes the geometry repair summary block.
    """
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="repair-report-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    report_html = (case_dir / "outputs" / "reports" / "report.html").read_text(encoding="utf-8")
    assert "Geometry repair" in report_html
    assert "Repair status: not_needed" in report_html
    assert "Watertight before: True" in report_html
    assert "Watertight after: True" in report_html
    # Spec §11.2 + §14: bulb region confirmation is always surfaced so
    # engineers can see whether they reviewed the auto-detected area.
    assert "Bulb region" in report_html
    assert "Confirmation source: auto_detected" in report_html
    # Spec §14: explicit Before/After comparison.
    assert "Before/After comparison" in report_html
    assert "Baseline axial extent" in report_html
    assert "Best candidate axial extent" in report_html


def test_run_vertical_slice_writes_case_package_archive(tmp_path: Path) -> None:
    """Spec §6.5: each completed case must yield an archived case package so
    engineers can share or store the full run in one file. The pipeline writes
    the zip into outputs/packages/ and records the path in artifacts_index.
    """
    import zipfile

    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="package-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    package_path = case_dir / "outputs" / "packages" / f"{summary.case_id}.zip"
    assert package_path.exists(), "Expected the case package archive to be written"
    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
    assert f"{summary.case_id}/case.json" in names
    assert f"{summary.case_id}/outputs/reports/report.html" in names

    artifacts_index = json.loads((case_dir / "artifacts_index.json").read_text(encoding="utf-8"))
    assert artifacts_index.get("case_package") == str(package_path)


def test_run_vertical_slice_applies_bulb_region_override_from_command(tmp_path: Path) -> None:
    """Spec §11.2: the user confirms or adjusts the auto-detected bulb area.
    When ``bulb_region_axis_min_override`` is set, the pipeline stores the
    confirmed value while preserving ``auto_axis_min`` for the report.
    """
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="confirm-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
            bulb_region_axis_min_override=1.5,
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    analysis = json.loads(
        (case_dir / "working" / "repaired" / "geometry_analysis.json").read_text(encoding="utf-8")
    )
    assert analysis["bulb_region"]["axis_min"] == pytest.approx(1.5)
    assert analysis["bulb_region"]["confirmation_source"] == "user_override"
    assert "auto_axis_min" in analysis["bulb_region"]


def test_run_vertical_slice_local_optimize_mode_completes_and_marks_candidates(
    tmp_path: Path,
) -> None:
    """Spec §11.4: launching with ``local_optimize`` must complete end-to-end
    and the persisted candidate_index must reflect the mode so the report and
    UI can distinguish local refinement runs from full regeneration.
    """
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="local-opt-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
            optimization_mode="local_optimize",
        ),
    )

    assert summary.status in {"completed", "completed_with_warnings"}
    case_dir = tmp_path / "projects" / summary.case_id
    candidate_index = json.loads((case_dir / "candidate_index.json").read_text(encoding="utf-8"))
    assert candidate_index, "Expected at least one candidate in local_optimize mode"
    for candidate in candidate_index:
        assert candidate["generation_profile"]["optimization_mode"] == "local_optimize"


def test_resume_vertical_slice_recovers_from_persisted_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §10 mandates that after a mid-pipeline failure, the application
    can resume the same case without re-entering metadata and without
    repeating successful stages.
    """
    from bulbopt.application.use_cases.run_vertical_slice import resume_vertical_slice
    from bulbopt.infrastructure.adapters.stub_evaluation import StubEvaluationAdapter

    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)
    project_root = tmp_path / "projects"

    # First attempt: force an evaluation failure so the case is flagged recoverable.
    original_evaluate = StubEvaluationAdapter.evaluate_candidates

    def broken_evaluate(self, *args, **kwargs):  # noqa: ARG001
        raise RuntimeError("evaluation outage")

    monkeypatch.setattr(StubEvaluationAdapter, "evaluate_candidates", broken_evaluate)

    with pytest.raises(RuntimeError, match="evaluation outage"):
        run_vertical_slice(
            project_root=project_root,
            command=CreateCaseCommand(
                case_name="resume-demo",
                source_path=str(source_path),
                vessel_length_m=142.0,
                vessel_beam_m=19.1,
                vessel_draft_m=6.0,
                displacement_t=8420.0,
                speed_knots=[18.0, 20.0],
            ),
        )

    failed_case_dirs = list(project_root.iterdir())
    assert len(failed_case_dirs) == 1
    case_id = failed_case_dirs[0].name
    case_dir = failed_case_dirs[0]
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert case_payload["status"] == "failed"
    assert case_payload["is_recoverable"] is True

    # Second attempt: restore evaluate_candidates and call resume_vertical_slice.
    monkeypatch.setattr(StubEvaluationAdapter, "evaluate_candidates", original_evaluate)

    summary = resume_vertical_slice(project_root=project_root, case_id=case_id)

    assert summary.case_id == case_id
    assert summary.status in {"completed", "completed_with_warnings"}

    case_payload_after = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert case_payload_after["status"] in {"completed", "completed_with_warnings"}
    assert case_payload_after["is_recoverable"] is False

    # prepare_geometry checkpoint from the first attempt should still be there
    # and the resumed run should NOT have overwritten it with a re-executed one.
    prepare_cp = case_dir / "working" / "checkpoints" / f"{case_id}-prepare_geometry.json"
    assert prepare_cp.exists()
    # The evaluation checkpoint was "failed" after the first attempt; the resume
    # must overwrite it with a completed payload.
    eval_cp = case_dir / "working" / "checkpoints" / f"{case_id}-evaluate_candidates.json"
    eval_payload = json.loads(eval_cp.read_text(encoding="utf-8"))
    assert eval_payload["status"] == "completed"


def test_run_vertical_slice_records_checkpoint_per_stage(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="checkpoint-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    case_dir = tmp_path / "projects" / summary.case_id
    checkpoints_dir = case_dir / "working" / "checkpoints"

    assert checkpoints_dir.exists()
    checkpoint_files = list(checkpoints_dir.glob("*.json"))
    assert checkpoint_files, "Expected per-stage checkpoint files after a successful run"

    stage_names = {
        path.stem.split(f"{summary.case_id}-", 1)[1] if path.stem.startswith(f"{summary.case_id}-") else path.stem
        for path in checkpoint_files
    }
    expected_stages = {
        "prepare_geometry",
        "generate_candidates",
        "evaluate_candidates",
        "rank_candidates",
        "openfoam_build_case",
        "openfoam_run_case",
        "build_html_report",
    }
    missing_stages = expected_stages - stage_names
    assert not missing_stages, f"Missing checkpoint stages: {sorted(missing_stages)}"

    for checkpoint_path in checkpoint_files:
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert payload["status"] == "completed", (
            f"Checkpoint {checkpoint_path.name} should be completed, got {payload['status']}"
        )


def test_run_vertical_slice_records_recoverable_checkpoint_on_stage_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "demo.stl"
    _write_valid_stl(source_path)
    project_root = tmp_path / "projects"

    from bulbopt.infrastructure.adapters.stub_evaluation import StubEvaluationAdapter

    def boom(self, *args, **kwargs):  # noqa: ARG001
        raise RuntimeError("evaluation failure")

    monkeypatch.setattr(StubEvaluationAdapter, "evaluate_candidates", boom)

    with pytest.raises(RuntimeError, match="evaluation failure"):
        run_vertical_slice(
            project_root=project_root,
            command=CreateCaseCommand(
                case_name="failing-stage-demo",
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
    case_dir = case_dirs[0]
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert case_payload["status"] == "failed"
    assert case_payload["is_recoverable"] is True

    checkpoints_dir = case_dir / "working" / "checkpoints"
    failing_checkpoint = next(
        (path for path in checkpoints_dir.glob("*.json") if "evaluate_candidates" in path.stem),
        None,
    )
    assert failing_checkpoint is not None, "Expected evaluate_candidates checkpoint to be written even on failure"
    payload = json.loads(failing_checkpoint.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["is_recoverable"] is True
    assert "evaluation failure" in payload["error"]
