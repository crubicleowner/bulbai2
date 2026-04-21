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
