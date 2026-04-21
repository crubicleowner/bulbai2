"""Tests for PyMeshFix-backed repair in StubGeometryAdapter.

These tests cover the contract between ``StubGeometryAdapter.prepare_geometry``
and the first-slice spec (§4.7, §12 criterion 4): the adapter validates the
imported mesh and performs basic repair when the mesh is not watertight. The
repair output is the canonical ``working/repaired/repaired.stl`` artifact used
by the rest of the pipeline, so downstream stages always see a repaired mesh.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

from bulbopt.infrastructure.adapters.stub_geometry import StubGeometryAdapter
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository
from bulbopt.domain.core.models import OptimizationCase


def _make_case_dir(tmp_path: Path) -> Path:
    repository = FilesystemProjectRepository(root_dir=tmp_path / "projects")
    case = OptimizationCase.new(case_id="case-repair", case_name="repair-demo")
    return repository.create_case(case)


def _make_case_dir_with_id(tmp_path: Path, case_id: str) -> Path:
    repository = FilesystemProjectRepository(root_dir=tmp_path / "projects")
    case = OptimizationCase.new(case_id=case_id, case_name=case_id)
    return repository.create_case(case)


def _write_watertight_stl(path: Path) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    assert mesh.is_watertight
    path.write_bytes(trimesh.exchange.stl.export_stl(mesh))
    return mesh


def _write_broken_stl(path: Path) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(4.0, 1.5, 1.0))
    broken = trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces[:-2])
    assert broken.is_watertight is False
    path.write_bytes(trimesh.exchange.stl.export_stl(broken))
    return broken


def test_prepare_geometry_leaves_watertight_mesh_untouched(tmp_path: Path) -> None:
    case_dir = _make_case_dir(tmp_path)
    source_path = tmp_path / "demo.stl"
    _write_watertight_stl(source_path)

    adapter = StubGeometryAdapter()
    analysis = adapter.prepare_geometry(case_dir, source_path)

    quality_report = analysis["quality_report"]
    assert quality_report["watertight"] is True
    assert quality_report["repaired"] is False
    assert quality_report["vertices_count_before"] == quality_report["vertices_count"]
    assert quality_report["faces_count_before"] == quality_report["faces_count"]

    repaired_path = case_dir / "working" / "repaired" / "repaired.stl"
    repaired_mesh = trimesh.load(repaired_path, force="mesh")
    assert isinstance(repaired_mesh, trimesh.Trimesh)
    assert repaired_mesh.is_watertight is True


def test_prepare_geometry_runs_pymeshfix_when_mesh_is_not_watertight(tmp_path: Path) -> None:
    case_dir = _make_case_dir(tmp_path)
    source_path = tmp_path / "broken.stl"
    broken = _write_broken_stl(source_path)

    adapter = StubGeometryAdapter()
    analysis = adapter.prepare_geometry(case_dir, source_path)

    quality_report = analysis["quality_report"]
    assert quality_report["watertight_before"] is False
    assert quality_report["repaired"] is True
    assert quality_report["watertight"] is True
    assert quality_report["faces_count_before"] == len(broken.faces)
    assert quality_report["faces_count"] >= len(broken.faces)

    repaired_path = case_dir / "working" / "repaired" / "repaired.stl"
    repaired_mesh = trimesh.load(repaired_path, force="mesh")
    assert isinstance(repaired_mesh, trimesh.Trimesh)
    assert repaired_mesh.is_watertight is True, (
        "Expected the on-disk repaired STL to be watertight so downstream stages "
        "always see a manifold mesh"
    )


def test_prepare_geometry_records_repair_artifact_in_quality_report(tmp_path: Path) -> None:
    case_dir = _make_case_dir(tmp_path)
    source_path = tmp_path / "broken.stl"
    _write_broken_stl(source_path)

    adapter = StubGeometryAdapter()
    adapter.prepare_geometry(case_dir, source_path)

    analysis_path = case_dir / "working" / "repaired" / "geometry_analysis.json"
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert payload["quality_report"]["repaired"] is True
    assert payload["quality_report"]["watertight"] is True
    assert payload["quality_report"]["watertight_before"] is False
    assert payload["quality_report"]["repair_status"] == "repaired"


def test_detect_bulb_region_returns_preview_without_creating_artifacts(tmp_path: Path) -> None:
    """Spec §11.2 "reviews the automatically detected bulb area" — the engineer
    needs to see the proposed region *before* committing to a full run. The
    detect-only path must not write any artifacts (no repaired.stl, no
    analysis.json, no artifacts_index.json), since no case exists yet.
    """
    source_path = tmp_path / "demo.stl"
    _write_watertight_stl(source_path)

    adapter = StubGeometryAdapter()
    preview = adapter.detect_bulb_region(source_path)

    assert "bulb_region" in preview
    assert "auto_axis_min" in preview["bulb_region"]
    assert "auto_axis_max" in preview["bulb_region"]
    assert preview["bulb_region"]["confirmation_source"] == "auto_detected"
    assert preview["quality_report"]["watertight"] is True

    # Nothing written to disk — the detect preview is pure.
    extra_entries = [item for item in tmp_path.iterdir() if item.name != "demo.stl"]
    assert extra_entries == [], (
        f"detect_bulb_region should not write artifacts, found: {extra_entries}"
    )


def test_prepare_geometry_accepts_user_bulb_region_override(tmp_path: Path) -> None:
    """Spec §11.2: the engineer must be able to review and *adjust* the
    auto-detected bulb area. ``bulb_region_override`` lets the UI pass a
    manual axis_min; the stored analysis preserves both the auto-detected
    value and the confirmed one so the report is engineering-honest.
    """
    case_dir = _make_case_dir(tmp_path)
    source_path = tmp_path / "demo.stl"
    _write_watertight_stl(source_path)

    adapter = StubGeometryAdapter()

    # First run: observe auto-detected axis_min.
    auto_analysis = adapter.prepare_geometry(case_dir, source_path)
    auto_axis_min = float(auto_analysis["bulb_region"]["axis_min"])
    auto_axis_max = float(auto_analysis["bulb_region"]["axis_max"])
    override_axis_min = auto_axis_min - 0.1

    # Second run on a fresh case: pass an override that differs from auto.
    case_dir_2 = _make_case_dir_with_id(tmp_path, "case-override")
    source_path_2 = tmp_path / "demo2.stl"
    _write_watertight_stl(source_path_2)

    analysis = adapter.prepare_geometry(
        case_dir_2,
        source_path_2,
        bulb_region_override={"axis_min": override_axis_min},
    )

    bulb_region = analysis["bulb_region"]
    assert bulb_region["axis_min"] == pytest.approx(override_axis_min)
    # axis_max is preserved (the engineer only adjusted the aft limit).
    assert bulb_region["axis_max"] == pytest.approx(auto_axis_max, rel=1e-6)
    # Auto-detected value stays visible for the report.
    assert bulb_region["auto_axis_min"] == pytest.approx(auto_axis_min, rel=1e-6)
    assert bulb_region["confirmation_source"] == "user_override"


def test_prepare_geometry_defaults_confirmation_source_to_auto(tmp_path: Path) -> None:
    case_dir = _make_case_dir(tmp_path)
    source_path = tmp_path / "demo.stl"
    _write_watertight_stl(source_path)

    adapter = StubGeometryAdapter()
    analysis = adapter.prepare_geometry(case_dir, source_path)

    assert analysis["bulb_region"]["confirmation_source"] == "auto_detected"
    assert "auto_axis_min" in analysis["bulb_region"]


def test_generate_candidates_local_optimize_uses_smaller_deformations(tmp_path: Path) -> None:
    """Spec §11.4: ``local_optimize`` morphs an existing bulb with constrained
    shape changes — the deformation amplitude must be strictly smaller than
    ``generate_new_bulb`` so the engineer gets local refinement, not bold
    variants.
    """
    case_dir = _make_case_dir(tmp_path)
    source_path = tmp_path / "demo.stl"
    _write_watertight_stl(source_path)

    adapter = StubGeometryAdapter()
    adapter.prepare_geometry(case_dir, source_path)

    generate_candidates = adapter.generate_candidates(
        case_dir, count=3, optimization_mode="generate_new_bulb"
    )
    local_candidates = adapter.generate_candidates(
        case_dir, count=3, optimization_mode="local_optimize"
    )

    for candidate in generate_candidates + local_candidates:
        assert Path(candidate["geometry_path"]).exists()

    generate_push = [float(c["generation_profile"]["axial_push"]) for c in generate_candidates]
    local_push = [float(c["generation_profile"]["axial_push"]) for c in local_candidates]

    assert max(local_push) < max(generate_push), (
        f"Expected local_optimize axial_push to be strictly smaller than "
        f"generate_new_bulb. Got local={local_push}, generate={generate_push}"
    )
    for candidate in local_candidates:
        assert candidate["generation_profile"]["optimization_mode"] == "local_optimize"
    for candidate in generate_candidates:
        assert candidate["generation_profile"]["optimization_mode"] == "generate_new_bulb"


def test_prepare_geometry_falls_back_when_pymeshfix_cannot_repair(tmp_path: Path) -> None:
    """When PyMeshFix produces an empty mesh (e.g. degenerate single-triangle
    input), ``prepare_geometry`` must not crash the pipeline: it preserves
    the original bytes in ``working/repaired/repaired.stl`` and flags the
    repair attempt as ``failed`` in ``quality_report`` so the report and UI
    can surface it honestly (per spec §14 "engineering-honest" reporting).
    """
    case_dir = _make_case_dir(tmp_path)
    source_path = tmp_path / "degenerate.stl"
    binary_stl = (
        (b"Binary STL demo" + b"\xff\xfe\xfa" + b"\x00" * 62)[:80]
        + (1).to_bytes(4, byteorder="little")
        + (b"\x80" * 50)
    )
    source_path.write_bytes(binary_stl)

    adapter = StubGeometryAdapter()
    analysis = adapter.prepare_geometry(case_dir, source_path)

    quality_report = analysis["quality_report"]
    assert quality_report["repaired"] is False
    assert quality_report["repair_status"] == "failed"
    assert quality_report["watertight_before"] is False

    repaired_path = case_dir / "working" / "repaired" / "repaired.stl"
    assert repaired_path.read_bytes() == binary_stl
