from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.domain.core.models import CaseStatus, OptimizationCase
from bulbopt.storage.filesystem.json_store import JsonStore
from bulbopt.storage.project_repository import filesystem_repository as repository_module
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def test_repository_creates_case_folder_and_writes_core_indexes(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="case-001", case_name="demo")

    case_dir = repository.create_case(case)

    assert case_dir == tmp_path / "case-001"
    assert case_dir.exists()
    assert (case_dir / "case.json").exists()
    assert (case_dir / "metadata.json").exists()
    assert (case_dir / "artifacts_index.json").exists()
    assert (case_dir / "candidate_index.json").exists()
    assert (case_dir / "evaluation_index.json").exists()


def test_repository_saves_candidate_index(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="case-001", case_name="demo")

    case_dir = repository.create_case(case)
    repository.save_candidate_index(
        case.case_id,
        [{"candidate_id": "cand-1", "geometry_path": "working/candidates/cand-1.stl", "status": "generated"}],
    )

    payload = json.loads((case_dir / "candidate_index.json").read_text(encoding="utf-8"))
    assert payload[0]["candidate_id"] == "cand-1"
    assert payload[0]["status"] == "generated"


def test_repository_persists_create_case_metadata(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="case-003", case_name="demo")
    command = CreateCaseCommand(
        case_name="demo",
        source_path="fixtures/demo.stl",
        vessel_length_m=142.0,
        vessel_beam_m=19.1,
        vessel_draft_m=6.0,
        displacement_t=8420.0,
        speed_knots=[18.0, 20.0],
    )

    case_dir = repository.create_case(case, metadata={"create_case_command": command})

    payload = JsonStore().read(case_dir / "metadata.json")

    assert payload == {
        "create_case_command": {
            "case_name": "demo",
            "source_path": "fixtures/demo.stl",
            "vessel_length_m": 142.0,
            "vessel_beam_m": 19.1,
            "vessel_draft_m": 6.0,
            "displacement_t": 8420.0,
            "speed_knots": [18.0, 20.0],
            "operational_profile_weights": None,
            "wave_height_m": 0.0,
            "wave_period_s": 0.0,
            "wave_scenario_heights_m": None,
            "wave_scenario_periods_s": None,
            "wave_scenario_weights": None,
            "calm_water_condition_weight": 0.7,
            "wave_condition_weight": 0.3,
            "import_format": "stl",
            "optimization_mode": "generate_new_bulb",
            "runtime_budget_hours": 8,
            "candidate_count": 3,
            "resistance_weight": 1.0,
            "axial_gain_weight": 0.8,
            "draft_reduction_weight": 0.1,
            "beam_growth_weight": 0.05,
            "max_volume_delta_pct": 4.5,
            "max_draft_delta_m": 0.05,
            "max_speed_balance_ratio": 4.0,
            "max_wave_penalty": 1.5,
            "reject_volume_delta_pct": 9.0,
            "reject_draft_delta_m": 0.1,
            "reject_speed_balance_ratio": 8.0,
            "reject_wave_penalty": 3.0,
        }
    }


def test_create_case_rejects_existing_case_folder(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="case-001", case_name="demo")

    repository.create_case(case)

    with pytest.raises(FileExistsError, match="case-001"):
        repository.create_case(case)


def test_save_candidate_index_rejects_missing_case_metadata(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case_dir = tmp_path / "case-001"
    case_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="case.json"):
        repository.save_candidate_index("case-001", [{"candidate_id": "cand-1"}])


def test_create_case_rejects_path_traversal_case_id(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="../escape", case_name="demo")

    with pytest.raises(ValueError, match="case_id"):
        repository.create_case(case)


def test_list_cases_returns_empty_list_when_root_is_missing(tmp_path: Path) -> None:
    """Before any case is created the repository root may not yet exist; listing
    must tolerate this and return an empty list rather than raising — spec §10
    implies restart must not require manual filesystem repair.
    """
    repository = FilesystemProjectRepository(root_dir=tmp_path / "does-not-exist-yet")

    assert repository.list_cases() == []


def test_list_cases_summarises_existing_cases_for_resume(tmp_path: Path) -> None:
    """Each case on disk must be surfaced with id, name, status, and recoverability
    flag so the UI can implement spec §10 "offer continuation" without re-reading
    each case.json by hand.
    """
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    completed_case = OptimizationCase.new(case_id="case-aaa", case_name="done")
    completed_case.status = CaseStatus.COMPLETED
    repository.create_case(completed_case)
    repository.save_case(completed_case)

    failed_case = OptimizationCase.new(case_id="case-bbb", case_name="failed")
    failed_case.status = CaseStatus.FAILED
    failed_case.is_recoverable = True
    repository.create_case(failed_case)
    repository.save_case(failed_case)

    # A stray non-case folder must not break listing (defensive per §10).
    (tmp_path / "not-a-case").mkdir()

    summaries = repository.list_cases()
    summaries_by_id = {summary["case_id"]: summary for summary in summaries}

    assert set(summaries_by_id) == {"case-aaa", "case-bbb"}
    assert summaries_by_id["case-aaa"]["status"] == "completed"
    assert summaries_by_id["case-aaa"]["is_recoverable"] is False
    assert summaries_by_id["case-aaa"]["case_name"] == "done"
    assert summaries_by_id["case-bbb"]["status"] == "failed"
    assert summaries_by_id["case-bbb"]["is_recoverable"] is True


def test_load_case_restores_optimization_case_from_case_json(tmp_path: Path) -> None:
    """Spec §10 resume requires re-hydrating a case from disk so the pipeline
    can continue without manual re-entry of metadata.
    """
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    original_case = OptimizationCase.new(case_id="case-resume", case_name="resume-demo")
    original_case.status = CaseStatus.FAILED
    original_case.is_recoverable = True
    original_case.source_path = "fixtures/resume.stl"
    repository.create_case(original_case)
    repository.save_case(original_case)

    loaded_case = repository.load_case("case-resume")

    assert loaded_case.case_id == "case-resume"
    assert loaded_case.case_name == "resume-demo"
    assert loaded_case.status is CaseStatus.FAILED
    assert loaded_case.is_recoverable is True
    assert loaded_case.source_path == "fixtures/resume.stl"


def test_load_case_raises_when_case_directory_is_missing(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)

    with pytest.raises(FileNotFoundError, match="case-missing"):
        repository.load_case("case-missing")


def test_load_create_case_command_reconstructs_dataclass_from_metadata(tmp_path: Path) -> None:
    """The resume path needs the original CreateCaseCommand to feed the same
    pipeline stages; metadata.json stores ``asdict(command)`` so the repository
    must reconstruct a real dataclass, not leak a plain dict.
    """
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="case-cmd", case_name="cmd-demo")
    command = CreateCaseCommand(
        case_name="cmd-demo",
        source_path="fixtures/demo.stl",
        vessel_length_m=142.0,
        vessel_beam_m=19.1,
        vessel_draft_m=6.0,
        displacement_t=8420.0,
        speed_knots=[18.0, 20.0],
    )
    repository.create_case(case, metadata={"create_case_command": command})

    reconstructed = repository.load_create_case_command("case-cmd")

    assert isinstance(reconstructed, CreateCaseCommand)
    assert reconstructed.case_name == "cmd-demo"
    assert reconstructed.source_path == "fixtures/demo.stl"
    assert reconstructed.speed_knots == [18.0, 20.0]
    assert reconstructed.candidate_count == 3


def test_save_case_refreshes_updated_at_before_persisting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="case-002", case_name="demo")
    repository.create_case(case)

    original_updated_at = case.updated_at
    refreshed_updated_at = datetime(2026, 4, 19, 12, 34, 56, tzinfo=timezone.utc).isoformat(
        timespec="seconds"
    )

    class FixedDateTime:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 4, 19, 12, 34, 56, tzinfo=tz)

    monkeypatch.setattr(repository_module, "datetime", FixedDateTime)

    case.status = CaseStatus.COMPLETED
    repository.save_case(case)

    payload = JsonStore().read(repository.case_dir(case.case_id) / "case.json")

    assert original_updated_at != refreshed_updated_at
    assert case.updated_at == refreshed_updated_at
    assert payload["updated_at"] == refreshed_updated_at
    assert payload["status"] == "completed"
