"""Append-only JSONL history store for (KrachtVector, Cd) pairs.

Design reference: 2026-04-23-bulbopt-mesh-quality-design.md §4 (L1).

Every completed high-fidelity evaluation writes one row
``{"parameters": {...}, "cd": float}`` to
``~/.bulbopt/history.jsonl`` (overridable). Subsequent night-runs load
this history to:

* Warm-start the NSGA-II initial population with the lowest-Cd points.
* Train a Gaussian Process that can replace the analytic mid-gate
  evaluator once enough history is accumulated.

The store deliberately uses plain JSONL so it's editable / inspectable /
trimmable with standard tools; no database needed.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from bulbopt.optimization.parametric.kracht_space import (
    KRACHT_PARAMETER_NAMES,
    KrachtVector,
)


def default_history_path() -> Path:
    """Default path: ``~/.bulbopt/history.jsonl``.

    Uses ``Path.home()`` which respects ``HOME`` / ``USERPROFILE`` on
    both POSIX and Windows.
    """
    return Path.home() / ".bulbopt" / "history.jsonl"


@dataclass(slots=True)
class HistoryStore:
    """Append-only history of (vector, Cd) pairs.

    Parameters
    ----------
    path:
        File path for the JSONL store. Defaults to
        ``~/.bulbopt/history.jsonl`` — callers (e.g. ProjectRepository)
        may override with a test path or a per-project location.
    """

    path: Path

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_history_path()

    # ---- writing ---------------------------------------------------------

    def record(self, vector: KrachtVector, cd: float) -> None:
        """Append one row to the JSONL store. Creates parents lazily."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "parameters": {
                name: float(vector.values[name]) for name in KRACHT_PARAMETER_NAMES
            },
            "cd": float(cd),
        }
        with self.path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(row) + "\n")

    # ---- reading ---------------------------------------------------------

    def load_all(self) -> List[Tuple[KrachtVector, float]]:
        """Return the full history as ``[(KrachtVector, cd), ...]``.

        Missing file returns an empty list. Malformed rows are silently
        skipped so a corrupt edit doesn't brick the optimizer.
        """
        if not self.path.exists():
            return []
        rows: List[Tuple[KrachtVector, float]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                parameters = payload["parameters"]
                cd = float(payload["cd"])
            except (KeyError, ValueError, json.JSONDecodeError):
                continue
            if not all(name in parameters for name in KRACHT_PARAMETER_NAMES):
                continue
            vec = KrachtVector(
                values={
                    name: float(parameters[name]) for name in KRACHT_PARAMETER_NAMES
                }
            )
            rows.append((vec, cd))
        return rows

    def top_k(self, n: int) -> List[KrachtVector]:
        """Return the ``n`` KrachtVectors with the lowest Cd.

        If history has fewer than ``n`` rows, returns all of them.
        Order is ascending Cd.
        """
        rows = self.load_all()
        rows.sort(key=lambda pair: pair[1])
        return [vec for vec, _cd in rows[: int(max(n, 0))]]
