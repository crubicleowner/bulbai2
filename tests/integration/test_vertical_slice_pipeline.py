from pathlib import Path

from bulbopt.app.bootstrap import bootstrap_application


def test_bootstrap_application_runs_vertical_slice_and_writes_report(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "demo.stl"
    source_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

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

    assert summary.status == "completed"
    assert len(case_dirs) == 1
    assert (case_dirs[0] / "outputs" / "reports" / "report.html").exists()
