"""Tests for CasePackageExporter (spec §6.5 archived case package)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from bulbopt.infrastructure.adapters.case_package_exporter import CasePackageExporter


def _build_fake_case(case_dir: Path, case_id: str) -> None:
    """Build a minimal case directory tree mirroring the real layout."""
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps({"case_id": case_id, "status": "completed"}),
        encoding="utf-8",
    )
    (case_dir / "metadata.json").write_text("{}", encoding="utf-8")
    (case_dir / "artifacts_index.json").write_text("{}", encoding="utf-8")
    (case_dir / "candidate_index.json").write_text("[]", encoding="utf-8")
    (case_dir / "evaluation_index.json").write_text("[]", encoding="utf-8")
    for relative in [
        "input",
        "working/repaired",
        "working/candidates",
        "working/checkpoints",
        "outputs/reports",
        "outputs/geometry",
        "logs",
    ]:
        (case_dir / relative).mkdir(parents=True, exist_ok=True)
    (case_dir / "input" / "hull.stl").write_bytes(b"solid demo\nendsolid demo\n")
    (case_dir / "working" / "repaired" / "repaired.stl").write_bytes(b"solid r\nendsolid r\n")
    (case_dir / "working" / "candidates" / "candidate-1.stl").write_bytes(b"solid c1\nendsolid c1\n")
    (case_dir / "outputs" / "reports" / "report.html").write_text(
        "<html>report</html>", encoding="utf-8"
    )
    (case_dir / "logs" / "case.log").write_text("started\n", encoding="utf-8")


def test_export_case_package_writes_zip_with_required_entries(tmp_path: Path) -> None:
    """The archive MUST include the minimum set of artifacts an engineer needs
    to reconstruct the run: case.json, metadata.json, artifacts/indices,
    inputs, repaired mesh, best candidate, and the HTML report.
    """
    case_id = "case-export"
    case_dir = tmp_path / "projects" / case_id
    _build_fake_case(case_dir, case_id)
    output_dir = tmp_path / "archives"

    exporter = CasePackageExporter()
    archive_path = exporter.export(case_dir, output_dir)

    assert archive_path.exists()
    assert archive_path.suffix == ".zip"
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    required = {
        f"{case_id}/case.json",
        f"{case_id}/metadata.json",
        f"{case_id}/artifacts_index.json",
        f"{case_id}/candidate_index.json",
        f"{case_id}/evaluation_index.json",
        f"{case_id}/input/hull.stl",
        f"{case_id}/working/repaired/repaired.stl",
        f"{case_id}/working/candidates/candidate-1.stl",
        f"{case_id}/outputs/reports/report.html",
        f"{case_id}/logs/case.log",
    }
    missing = required - names
    assert not missing, f"Archive is missing required entries: {missing}"


def test_export_case_package_skips_checkpoints_by_default(tmp_path: Path) -> None:
    """working/checkpoints are runtime-only; archives should be lean. The
    engineer can still include them by passing include_checkpoints=True.
    """
    case_id = "case-chk"
    case_dir = tmp_path / "projects" / case_id
    _build_fake_case(case_dir, case_id)
    (case_dir / "working" / "checkpoints" / f"{case_id}-prepare_geometry.json").write_text(
        "{}", encoding="utf-8"
    )
    default_dir = tmp_path / "archives-default"
    verbose_dir = tmp_path / "archives-verbose"

    exporter = CasePackageExporter()
    default_archive = exporter.export(case_dir, default_dir)
    verbose_archive = exporter.export(case_dir, verbose_dir, include_checkpoints=True)

    with zipfile.ZipFile(default_archive) as archive:
        default_names = set(archive.namelist())
    with zipfile.ZipFile(verbose_archive) as archive:
        verbose_names = set(archive.namelist())

    checkpoint_entry = f"{case_id}/working/checkpoints/{case_id}-prepare_geometry.json"
    assert checkpoint_entry not in default_names
    assert checkpoint_entry in verbose_names


def test_export_case_package_rejects_missing_case_directory(tmp_path: Path) -> None:
    exporter = CasePackageExporter()
    with pytest.raises(FileNotFoundError, match="case-does-not-exist"):
        exporter.export(tmp_path / "case-does-not-exist", tmp_path / "archives")
