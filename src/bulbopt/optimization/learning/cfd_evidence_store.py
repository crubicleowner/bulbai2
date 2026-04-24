"""Append-only evidence store for high-fidelity CFD evaluations."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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
