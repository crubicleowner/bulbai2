"""Append-only evidence store for high-fidelity CFD evaluations."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from bulbopt.optimization.parametric.kracht_space import (
    KRACHT_PARAMETER_NAMES,
    KrachtVector,
)


@dataclass(slots=True)
class CFDEvidenceStore:
    """Persist machine-readable CFD evidence as JSONL.

    The store intentionally stays filesystem-native so engineers can inspect,
    diff, archive, or feed the rows into ML tooling without a database.
    """

    path: Path

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append_many(self, rows: Iterable[dict]) -> None:
        rows = list(rows)
        if not rows:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    def write_all(self, rows: Iterable[dict]) -> None:
        rows = list(rows)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    def load_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        loaded: list[dict] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                loaded.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return loaded

    def top_k_safe_warm_start(self, n: int) -> list[KrachtVector]:
        """Return verified improving candidates ordered by lowest final Cd."""
        rows = []
        for row in self.load_all():
            if row.get("record_type") != "candidate":
                continue
            if row.get("engineering_valid") is not True:
                continue
            improvement = row.get("improvement_percent")
            if improvement is None or float(improvement) <= 0.0:
                continue
            final_cd = row.get("final_cd")
            if final_cd is None:
                continue
            parameters = row.get("parameters") or {}
            if not all(name in parameters for name in KRACHT_PARAMETER_NAMES):
                continue
            try:
                vector = KrachtVector(
                    values={
                        name: float(parameters[name])
                        for name in KRACHT_PARAMETER_NAMES
                    }
                )
                rows.append((vector, float(final_cd)))
            except (TypeError, ValueError):
                continue

        rows.sort(key=lambda pair: pair[1])
        return [vector for vector, _cd in rows[: int(max(n, 0))]]

    def surrogate_training_pairs(self) -> list[Tuple[KrachtVector, float]]:
        """Return finite, engineering-valid CFD rows for surrogate training."""
        rows: list[Tuple[KrachtVector, float]] = []
        for row in self.load_all():
            if row.get("record_type") != "candidate":
                continue
            if row.get("engineering_valid") is not True:
                continue
            final_cd = row.get("final_cd")
            if final_cd is None:
                continue
            try:
                cd = float(final_cd)
            except (TypeError, ValueError):
                continue
            if cd >= 1e8:
                continue
            parameters = row.get("parameters") or {}
            if not all(name in parameters for name in KRACHT_PARAMETER_NAMES):
                continue
            try:
                rows.append(
                    (
                        KrachtVector(
                            values={
                                name: float(parameters[name])
                                for name in KRACHT_PARAMETER_NAMES
                            }
                        ),
                        cd,
                    )
                )
            except (TypeError, ValueError):
                continue
        return rows
