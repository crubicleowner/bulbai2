"""Tests for the Kracht/Cd history store.

Design reference: 2026-04-23-bulbopt-mesh-quality-design.md §4 (L1).

The store appends every (KrachtVector, high-fidelity Cd) pair to a JSONL
file so future night-runs can warm-start NSGA-II and train a GP surrogate.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bulbopt.optimization.learning.history_store import HistoryStore
from bulbopt.optimization.parametric.kracht_space import (
    KRACHT_PARAMETER_NAMES,
    KrachtDesignSpace,
    KrachtVector,
)


def _vector(**overrides: float) -> KrachtVector:
    space = KrachtDesignSpace()
    # pick the middle of each range as the default
    values = {
        name: 0.5 * (lo + hi)
        for name, (lo, hi) in space.bounds.items()
    }
    values.update(overrides)
    return KrachtVector(values=values)


def test_history_store_records_and_reloads_vector_cd_pair(tmp_path: Path) -> None:
    store = HistoryStore(path=tmp_path / "history.jsonl")
    v = _vector()
    store.record(v, cd=0.42)

    reloaded = store.load_all()
    assert len(reloaded) == 1
    vec, cd = reloaded[0]
    assert cd == pytest.approx(0.42)
    for name in KRACHT_PARAMETER_NAMES:
        assert vec.values[name] == pytest.approx(v.values[name])


def test_history_store_append_does_not_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    store = HistoryStore(path=path)
    store.record(_vector(length_ratio=0.02), cd=0.40)
    store.record(_vector(length_ratio=0.03), cd=0.35)

    # Reopen to confirm persistence.
    store2 = HistoryStore(path=path)
    rows = store2.load_all()
    assert len(rows) == 2
    assert rows[0][1] == pytest.approx(0.40)
    assert rows[1][1] == pytest.approx(0.35)


def test_history_store_top_k_returns_lowest_cd_first(tmp_path: Path) -> None:
    store = HistoryStore(path=tmp_path / "history.jsonl")
    store.record(_vector(length_ratio=0.02), cd=0.50)
    store.record(_vector(length_ratio=0.03), cd=0.40)
    store.record(_vector(length_ratio=0.04), cd=0.45)

    top2 = store.top_k(2)
    assert len(top2) == 2
    # Lowest Cd first.
    assert top2[0].values["length_ratio"] == pytest.approx(0.03)
    assert top2[1].values["length_ratio"] == pytest.approx(0.04)


def test_history_store_top_k_clamps_to_available(tmp_path: Path) -> None:
    store = HistoryStore(path=tmp_path / "history.jsonl")
    store.record(_vector(), cd=0.5)
    # k larger than stored points just returns what we have.
    assert len(store.top_k(10)) == 1


def test_history_store_load_all_on_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.jsonl"
    store = HistoryStore(path=missing)
    assert store.load_all() == []


def test_history_store_respects_explicit_path(tmp_path: Path) -> None:
    """Default path is ~/.bulbopt/history.jsonl but the constructor
    allows override (so tests and ProjectRepository can redirect)."""
    custom = tmp_path / "custom" / "hist.jsonl"
    store = HistoryStore(path=custom)
    store.record(_vector(), cd=0.4)
    assert custom.exists()
    assert len(custom.read_text(encoding="utf-8").splitlines()) == 1
