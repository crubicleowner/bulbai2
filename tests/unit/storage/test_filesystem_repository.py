import json
from pathlib import Path

from bulbopt.domain.core.models import OptimizationCase
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
