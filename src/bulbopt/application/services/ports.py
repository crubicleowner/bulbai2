from __future__ import annotations

from pathlib import Path
from typing import Protocol


class GeometryService(Protocol):
    def prepare_geometry(self, case_dir: Path, source_path: Path) -> dict: ...

    def generate_candidates(self, case_dir: Path, count: int) -> list[dict]: ...


class EvaluationService(Protocol):
    def evaluate_candidates(self, candidates: list[dict]) -> list[dict]: ...


class OptimizationService(Protocol):
    def choose_best(self, evaluated_candidates: list[dict]) -> dict: ...


class ReportService(Protocol):
    def build_html_report(self, case_dir: Path, context: dict) -> Path: ...
