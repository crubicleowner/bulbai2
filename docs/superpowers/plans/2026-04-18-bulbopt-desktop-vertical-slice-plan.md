# BulbOpt Desktop Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first honest end-to-end `BulbOpt Desktop` slice: `STL` import, case persistence, geometry validation/repair stubs, candidate generation, simplified evaluation, ranking, background execution, recovery metadata, and `HTML` report export.

**Architecture:** The implementation uses a modular `PySide6 + Python` desktop shell backed by a clean domain model, file-based case storage, a local worker execution layer, and adapter-based engineering integrations. The first slice stays `STL-first`, keeps `OpenFOAM` optional, and uses stub-friendly geometry/evaluation services so the system is runnable before heavy CFD integrations land.

**Tech Stack:** `Python 3.12+`, `PySide6`, `jinja2`, `trimesh`, `pyvista`, `pymeshfix`, `numpy`, `pytest`

---

## File Structure

Create or modify the following files for the first slice.

- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/bulbopt/__init__.py`
- Create: `src/bulbopt/app/bootstrap.py`
- Create: `src/bulbopt/app/main.py`
- Create: `src/bulbopt/application/contracts/models.py`
- Create: `src/bulbopt/application/services/ports.py`
- Create: `src/bulbopt/application/use_cases/create_case.py`
- Create: `src/bulbopt/application/use_cases/run_vertical_slice.py`
- Create: `src/bulbopt/domain/core/models.py`
- Create: `src/bulbopt/storage/filesystem/json_store.py`
- Create: `src/bulbopt/storage/project_repository/filesystem_repository.py`
- Create: `src/bulbopt/execution/checkpoints/file_checkpoint_store.py`
- Create: `src/bulbopt/execution/worker/local_worker.py`
- Create: `src/bulbopt/infrastructure/config/settings.py`
- Create: `src/bulbopt/infrastructure/adapters/stub_geometry.py`
- Create: `src/bulbopt/infrastructure/adapters/stub_evaluation.py`
- Create: `src/bulbopt/infrastructure/adapters/stub_optimization.py`
- Create: `src/bulbopt/infrastructure/adapters/html_report.py`
- Create: `src/bulbopt/reporting/templates/report.html.j2`
- Create: `src/bulbopt/ui/desktop/main_window.py`
- Create: `src/bulbopt/ui/desktop/case_wizard.py`
- Create: `tests/unit/domain/test_models.py`
- Create: `tests/unit/storage/test_filesystem_repository.py`
- Create: `tests/unit/execution/test_local_worker.py`
- Create: `tests/unit/application/test_run_vertical_slice.py`
- Create: `tests/integration/test_vertical_slice_pipeline.py`

Notes:

- The workspace is not currently a git repository, so this plan initializes git in Task 1.
- `STEP`, `PDF`, `OpenFOAM`, and `high fidelity` are intentionally excluded from this first slice.

### Task 1: Bootstrap The Repository And Runtime

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `src/bulbopt/__init__.py`
- Create: `src/bulbopt/app/main.py`
- Test: `tests/unit/application/test_bootstrap_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/unit/application/test_bootstrap_smoke.py
from bulbopt.app.main import build_cli_banner


def test_build_cli_banner_contains_product_name() -> None:
    banner = build_cli_banner()

    assert "BulbOpt Desktop" in banner
    assert "STL-first" in banner
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest tests/unit/application/test_bootstrap_smoke.py -v
```

Expected: FAIL with `ModuleNotFoundError` because the package does not exist yet.

- [ ] **Step 3: Create the packaging and entry-point files**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "bulbopt-desktop"
version = "0.1.0"
description = "Desktop tool for bulbous bow generation and optimization"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "jinja2>=3.1",
  "numpy>=2.2",
  "PySide6>=6.8",
  "pymeshfix>=0.17",
  "pyvista>=0.44",
  "trimesh>=4.6",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```gitignore
# .gitignore
__pycache__/
.pytest_cache/
.venv/
dist/
build/
*.pyc
*.pyo
*.pyd
bulbopt_projects/
```

```markdown
# README.md

## BulbOpt Desktop

`BulbOpt Desktop` is a modular desktop application for STL-first bulbous bow generation, evaluation, and reporting.

Current scope:

- local file-based cases
- background worker execution
- geometry and evaluation stubs
- HTML report export
```

```python
# src/bulbopt/__init__.py
__all__ = ["__version__"]

__version__ = "0.1.0"
```

```python
# src/bulbopt/app/main.py
def build_cli_banner() -> str:
    return "BulbOpt Desktop | STL-first vertical slice"


if __name__ == "__main__":
    print(build_cli_banner())
```

- [ ] **Step 4: Run the smoke test to verify it passes**

Run:

```powershell
python -m pytest tests/unit/application/test_bootstrap_smoke.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Initialize git and commit the bootstrap**

Run:

```powershell
git init
git add pyproject.toml .gitignore README.md src tests
git commit -m "chore: bootstrap bulbopt desktop repository"
```

Expected: repository initialized and first commit created.

### Task 2: Define Core Contracts And Domain Models

**Files:**
- Create: `src/bulbopt/application/contracts/models.py`
- Create: `src/bulbopt/domain/core/models.py`
- Test: `tests/unit/domain/test_models.py`

- [ ] **Step 1: Write the failing domain-model tests**

```python
# tests/unit/domain/test_models.py
from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.domain.core.models import CandidateVariant, CaseStatus, OptimizationCase


def test_create_case_command_defaults_to_stl_first_mode() -> None:
    command = CreateCaseCommand(
        case_name="dtmb-5415-demo",
        source_path="fixtures/dtmb5415.stl",
        vessel_length_m=142.0,
        vessel_beam_m=19.1,
        vessel_draft_m=6.0,
        displacement_t=8420.0,
        speed_knots=[18.0, 20.0],
    )

    assert command.import_format == "stl"
    assert command.optimization_mode == "generate_new_bulb"


def test_optimization_case_starts_in_draft_status() -> None:
    case = OptimizationCase.new(case_id="case-001", case_name="demo")

    assert case.status is CaseStatus.DRAFT
    assert case.is_recoverable is False


def test_candidate_variant_tracks_retry_metadata() -> None:
    candidate = CandidateVariant(candidate_id="cand-1", geometry_path="working/candidates/cand-1.stl")

    assert candidate.retry_count == 0
    assert candidate.can_retry is True
    assert candidate.error_code is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m pytest tests/unit/domain/test_models.py -v
```

Expected: FAIL because contracts and domain models do not exist yet.

- [ ] **Step 3: Implement the contracts and domain models**

```python
# src/bulbopt/application/contracts/models.py
from dataclasses import dataclass, field


@dataclass(slots=True)
class CreateCaseCommand:
    case_name: str
    source_path: str
    vessel_length_m: float
    vessel_beam_m: float
    vessel_draft_m: float
    displacement_t: float
    speed_knots: list[float]
    import_format: str = "stl"
    optimization_mode: str = "generate_new_bulb"
    runtime_budget_hours: int = 8


@dataclass(slots=True)
class CaseSummary:
    case_id: str
    case_name: str
    status: str
    best_candidate_id: str | None = None
```

```python
# src/bulbopt/domain/core/models.py
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class CaseStatus(str, Enum):
    DRAFT = "draft"
    IMPORTED = "imported"
    VALIDATED = "validated"
    REPAIRING_GEOMETRY = "repairing_geometry"
    GEOMETRY_READY = "geometry_ready"
    BULB_REGION_PENDING_CONFIRMATION = "bulb_region_pending_confirmation"
    READY_FOR_OPTIMIZATION = "ready_for_optimization"
    RUNNING_FAST_SCREENING = "running_fast_screening"
    RUNNING_MID_FIDELITY = "running_mid_fidelity"
    RUNNING_HIGH_FIDELITY = "running_high_fidelity"
    ASSEMBLING_RESULTS = "assembling_results"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    PAUSED = "paused"
    FAILED = "failed"


@dataclass(slots=True)
class CandidateVariant:
    candidate_id: str
    geometry_path: str
    status: str = "generated"
    score: float | None = None
    error_code: str | None = None
    retry_count: int = 0
    can_retry: bool = True


@dataclass(slots=True)
class OptimizationCase:
    case_id: str
    case_name: str
    status: CaseStatus
    created_at: str
    updated_at: str
    is_recoverable: bool
    source_path: str | None = None
    candidates: list[CandidateVariant] = field(default_factory=list)

    @classmethod
    def new(cls, case_id: str, case_name: str) -> "OptimizationCase":
        now = datetime.now(UTC).isoformat()
        return cls(
            case_id=case_id,
            case_name=case_name,
            status=CaseStatus.DRAFT,
            created_at=now,
            updated_at=now,
            is_recoverable=False,
        )
```

- [ ] **Step 4: Run the domain-model tests to verify they pass**

Run:

```powershell
python -m pytest tests/unit/domain/test_models.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit the contracts and domain layer**

Run:

```powershell
git add src/bulbopt/application/contracts/models.py src/bulbopt/domain/core/models.py tests/unit/domain/test_models.py
git commit -m "feat: add core case and candidate models"
```

### Task 3: Implement File-Based Case Storage

**Files:**
- Create: `src/bulbopt/storage/filesystem/json_store.py`
- Create: `src/bulbopt/storage/project_repository/filesystem_repository.py`
- Test: `tests/unit/storage/test_filesystem_repository.py`

- [ ] **Step 1: Write the failing repository tests**

```python
# tests/unit/storage/test_filesystem_repository.py
import json
from pathlib import Path

from bulbopt.domain.core.models import OptimizationCase
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def test_repository_creates_case_folder_and_case_json(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="case-001", case_name="demo")

    case_path = repository.create_case(case)

    assert case_path.exists()
    assert (case_path / "case.json").exists()
    assert (case_path / "metadata.json").exists()
    assert (case_path / "artifacts_index.json").exists()


def test_repository_saves_candidate_index(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="case-001", case_name="demo")
    case.candidates.append({"candidate_id": "cand-1"})

    case_path = repository.create_case(case)
    repository.save_candidate_index(case.case_id, [{"candidate_id": "cand-1", "status": "generated"}])

    data = json.loads((case_path / "candidate_index.json").read_text(encoding="utf-8"))
    assert data[0]["candidate_id"] == "cand-1"
```

- [ ] **Step 2: Run the repository tests to verify they fail**

Run:

```powershell
python -m pytest tests/unit/storage/test_filesystem_repository.py -v
```

Expected: FAIL because the repository and json store do not exist yet.

- [ ] **Step 3: Implement the JSON store and project repository**

```python
# src/bulbopt/storage/filesystem/json_store.py
import json
from pathlib import Path
from typing import Any


class JsonStore:
    def write(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def read(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))
```

```python
# src/bulbopt/storage/project_repository/filesystem_repository.py
from dataclasses import asdict
from pathlib import Path

from bulbopt.domain.core.models import OptimizationCase
from bulbopt.storage.filesystem.json_store import JsonStore


class FilesystemProjectRepository:
    def __init__(self, root_dir: Path, json_store: JsonStore | None = None) -> None:
        self.root_dir = root_dir
        self.json_store = json_store or JsonStore()

    def case_dir(self, case_id: str) -> Path:
        return self.root_dir / case_id

    def create_case(self, case: OptimizationCase) -> Path:
        case_path = self.case_dir(case.case_id)
        for folder in [
            "input",
            "working/repaired",
            "working/masks",
            "working/candidates",
            "working/evaluation",
            "working/checkpoints",
            "outputs/geometry",
            "outputs/reports",
            "outputs/plots",
            "outputs/tables",
            "logs",
        ]:
            (case_path / folder).mkdir(parents=True, exist_ok=True)

        self.json_store.write(case_path / "case.json", asdict(case))
        self.json_store.write(case_path / "metadata.json", {})
        self.json_store.write(case_path / "artifacts_index.json", {})
        self.json_store.write(case_path / "candidate_index.json", [])
        self.json_store.write(case_path / "evaluation_index.json", [])
        return case_path

    def save_candidate_index(self, case_id: str, payload: list[dict]) -> None:
        self.json_store.write(self.case_dir(case_id) / "candidate_index.json", payload)
```

- [ ] **Step 4: Fix the test input to match the typed domain model and rerun**

Replace the second test body with:

```python
def test_repository_saves_candidate_index(tmp_path: Path) -> None:
    repository = FilesystemProjectRepository(root_dir=tmp_path)
    case = OptimizationCase.new(case_id="case-001", case_name="demo")

    case_path = repository.create_case(case)
    repository.save_candidate_index(case.case_id, [{"candidate_id": "cand-1", "status": "generated"}])

    data = json.loads((case_path / "candidate_index.json").read_text(encoding="utf-8"))
    assert data[0]["candidate_id"] == "cand-1"
```

Run:

```powershell
python -m pytest tests/unit/storage/test_filesystem_repository.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit the storage layer**

Run:

```powershell
git add src/bulbopt/storage tests/unit/storage/test_filesystem_repository.py
git commit -m "feat: add filesystem project repository"
```

### Task 4: Add The Worker And Checkpoint Layer

**Files:**
- Create: `src/bulbopt/execution/checkpoints/file_checkpoint_store.py`
- Create: `src/bulbopt/execution/worker/local_worker.py`
- Test: `tests/unit/execution/test_local_worker.py`

- [ ] **Step 1: Write the failing worker tests**

```python
# tests/unit/execution/test_local_worker.py
from pathlib import Path

from bulbopt.execution.checkpoints.file_checkpoint_store import FileCheckpointStore
from bulbopt.execution.worker.local_worker import LocalWorker


def test_local_worker_runs_job_and_returns_result(tmp_path: Path) -> None:
    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    result = worker.run("case-001", "stage-1", lambda: {"status": "ok"})

    assert result["status"] == "ok"
    assert (tmp_path / "case-001-stage-1.json").exists()


def test_local_worker_marks_failure_as_recoverable(tmp_path: Path) -> None:
    checkpoints = FileCheckpointStore(root_dir=tmp_path)
    worker = LocalWorker(checkpoint_store=checkpoints)

    result = worker.run("case-001", "stage-1", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    assert result["status"] == "failed"
    assert result["is_recoverable"] is True
```

- [ ] **Step 2: Run the worker tests to verify they fail**

Run:

```powershell
python -m pytest tests/unit/execution/test_local_worker.py -v
```

Expected: FAIL because the checkpoint store and worker do not exist yet.

- [ ] **Step 3: Implement the checkpoint store and worker**

```python
# src/bulbopt/execution/checkpoints/file_checkpoint_store.py
from pathlib import Path

from bulbopt.storage.filesystem.json_store import JsonStore


class FileCheckpointStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.json_store = JsonStore()

    def save(self, case_id: str, stage_name: str, payload: dict) -> Path:
        path = self.root_dir / f"{case_id}-{stage_name}.json"
        self.json_store.write(path, payload)
        return path
```

```python
# src/bulbopt/execution/worker/local_worker.py
from collections.abc import Callable
from typing import Any

from bulbopt.execution.checkpoints.file_checkpoint_store import FileCheckpointStore


class LocalWorker:
    def __init__(self, checkpoint_store: FileCheckpointStore) -> None:
        self.checkpoint_store = checkpoint_store

    def run(self, case_id: str, stage_name: str, job: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            result = job()
            self.checkpoint_store.save(case_id, stage_name, {"status": "completed", "result": result})
            return result
        except Exception as exc:
            payload = {"status": "failed", "error": str(exc), "is_recoverable": True}
            self.checkpoint_store.save(case_id, stage_name, payload)
            return payload
```

- [ ] **Step 4: Run the worker tests to verify they pass**

Run:

```powershell
python -m pytest tests/unit/execution/test_local_worker.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit the worker layer**

Run:

```powershell
git add src/bulbopt/execution tests/unit/execution/test_local_worker.py
git commit -m "feat: add local worker and checkpoint persistence"
```

### Task 5: Implement Stub Geometry, Evaluation, Optimization, And Reporting Services

**Files:**
- Create: `src/bulbopt/application/services/ports.py`
- Create: `src/bulbopt/infrastructure/adapters/stub_geometry.py`
- Create: `src/bulbopt/infrastructure/adapters/stub_evaluation.py`
- Create: `src/bulbopt/infrastructure/adapters/stub_optimization.py`
- Create: `src/bulbopt/infrastructure/adapters/html_report.py`
- Create: `src/bulbopt/reporting/templates/report.html.j2`
- Test: `tests/unit/application/test_run_vertical_slice.py`

- [ ] **Step 1: Write the failing service-level test**

```python
# tests/unit/application/test_run_vertical_slice.py
from pathlib import Path

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.application.use_cases.run_vertical_slice import run_vertical_slice


def test_run_vertical_slice_returns_completed_summary(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    source_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    summary = run_vertical_slice(
        project_root=tmp_path / "projects",
        command=CreateCaseCommand(
            case_name="dtmb-demo",
            source_path=str(source_path),
            vessel_length_m=142.0,
            vessel_beam_m=19.1,
            vessel_draft_m=6.0,
            displacement_t=8420.0,
            speed_knots=[18.0, 20.0],
        ),
    )

    assert summary.status == "completed"
    assert summary.best_candidate_id is not None
```

- [ ] **Step 2: Run the service-level test to verify it fails**

Run:

```powershell
python -m pytest tests/unit/application/test_run_vertical_slice.py -v
```

Expected: FAIL because the ports, adapters, and use case do not exist yet.

- [ ] **Step 3: Implement the service ports and stub adapters**

```python
# src/bulbopt/application/services/ports.py
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
```

```python
# src/bulbopt/infrastructure/adapters/stub_geometry.py
from pathlib import Path


class StubGeometryAdapter:
    def prepare_geometry(self, case_dir: Path, source_path: Path) -> dict:
        repaired_path = case_dir / "working" / "repaired" / "repaired.stl"
        repaired_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        return {
            "quality_report": {"watertight": False, "repaired": True},
            "repaired_path": str(repaired_path),
            "bulb_region": {"x_min": 0.0, "x_max": 5.0},
        }

    def generate_candidates(self, case_dir: Path, count: int) -> list[dict]:
        candidates: list[dict] = []
        for index in range(count):
            candidate_path = case_dir / "working" / "candidates" / f"candidate-{index + 1}.stl"
            candidate_path.write_text(f"solid candidate-{index + 1}\nendsolid candidate-{index + 1}\n", encoding="utf-8")
            candidates.append(
                {
                    "candidate_id": f"candidate-{index + 1}",
                    "geometry_path": str(candidate_path),
                    "status": "generated",
                }
            )
        return candidates
```

```python
# src/bulbopt/infrastructure/adapters/stub_evaluation.py
class StubEvaluationAdapter:
    def evaluate_candidates(self, candidates: list[dict]) -> list[dict]:
        evaluated: list[dict] = []
        for index, candidate in enumerate(candidates, start=1):
            evaluated.append(
                {
                    **candidate,
                    "status": "mid_score_ready",
                    "fast_score": 1.0 / index,
                    "mid_score": 10.0 - index,
                }
            )
        return evaluated
```

```python
# src/bulbopt/infrastructure/adapters/stub_optimization.py
class StubOptimizationAdapter:
    def choose_best(self, evaluated_candidates: list[dict]) -> dict:
        return sorted(evaluated_candidates, key=lambda item: item["mid_score"])[0]
```

```python
# src/bulbopt/infrastructure/adapters/html_report.py
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


class HtmlReportAdapter:
    def __init__(self, template_root: Path) -> None:
        self.environment = Environment(
            loader=FileSystemLoader(template_root),
            autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        )

    def build_html_report(self, case_dir: Path, context: dict) -> Path:
        template = self.environment.get_template("report.html.j2")
        report_path = case_dir / "outputs" / "reports" / "report.html"
        report_path.write_text(template.render(**context), encoding="utf-8")
        return report_path
```

```html
<!-- src/bulbopt/reporting/templates/report.html.j2 -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>BulbOpt Desktop Report</title>
  </head>
  <body>
    <h1>BulbOpt Desktop Report</h1>
    <p>Case: {{ case_name }}</p>
    <p>Status: {{ status }}</p>
    <p>Best candidate: {{ best_candidate_id }}</p>
    <p>OpenFOAM available: {{ openfoam_available }}</p>
    <p>High fidelity used: {{ high_fidelity_used }}</p>
  </body>
</html>
```

- [ ] **Step 4: Implement the run-vertical-slice use case and rerun the test**

```python
# src/bulbopt/application/use_cases/run_vertical_slice.py
from pathlib import Path
from uuid import uuid4

from bulbopt.application.contracts.models import CaseSummary, CreateCaseCommand
from bulbopt.domain.core.models import CaseStatus, OptimizationCase
from bulbopt.infrastructure.adapters.html_report import HtmlReportAdapter
from bulbopt.infrastructure.adapters.stub_evaluation import StubEvaluationAdapter
from bulbopt.infrastructure.adapters.stub_geometry import StubGeometryAdapter
from bulbopt.infrastructure.adapters.stub_optimization import StubOptimizationAdapter
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def run_vertical_slice(project_root: Path, command: CreateCaseCommand) -> CaseSummary:
    repository = FilesystemProjectRepository(root_dir=project_root)
    case = OptimizationCase.new(case_id=f"case-{uuid4().hex[:8]}", case_name=command.case_name)
    case.source_path = command.source_path
    case.status = CaseStatus.IMPORTED
    case_dir = repository.create_case(case)

    geometry = StubGeometryAdapter()
    evaluation = StubEvaluationAdapter()
    optimization = StubOptimizationAdapter()
    report = HtmlReportAdapter(template_root=Path("src/bulbopt/reporting/templates"))

    geometry.prepare_geometry(case_dir, Path(command.source_path))
    candidates = geometry.generate_candidates(case_dir, count=3)
    repository.save_candidate_index(case.case_id, candidates)

    evaluated = evaluation.evaluate_candidates(candidates)
    best_candidate = optimization.choose_best(evaluated)
    report.build_html_report(
        case_dir,
        {
            "case_name": case.case_name,
            "status": "completed",
            "best_candidate_id": best_candidate["candidate_id"],
            "openfoam_available": False,
            "high_fidelity_used": False,
        },
    )

    case.status = CaseStatus.COMPLETED
    return CaseSummary(case_id=case.case_id, case_name=case.case_name, status="completed", best_candidate_id=best_candidate["candidate_id"])
```

Run:

```powershell
python -m pytest tests/unit/application/test_run_vertical_slice.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit the stub engineering services**

Run:

```powershell
git add src/bulbopt/application/services src/bulbopt/application/use_cases/run_vertical_slice.py src/bulbopt/infrastructure/adapters src/bulbopt/reporting/templates tests/unit/application/test_run_vertical_slice.py
git commit -m "feat: add stub geometry evaluation and reporting pipeline"
```

### Task 6: Add The Case-Creation Use Case And Settings Wiring

**Files:**
- Create: `src/bulbopt/infrastructure/config/settings.py`
- Create: `src/bulbopt/application/use_cases/create_case.py`
- Modify: `src/bulbopt/app/bootstrap.py`
- Test: `tests/integration/test_vertical_slice_pipeline.py`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/integration/test_vertical_slice_pipeline.py
from pathlib import Path

from bulbopt.app.bootstrap import bootstrap_application


def test_bootstrap_application_runs_vertical_slice_and_writes_report(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    source_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    app = bootstrap_application(project_root=tmp_path / "projects")
    summary = app["run_vertical_slice"](
        case_name="demo-case",
        source_path=str(source_path),
        vessel_length_m=142.0,
        vessel_beam_m=19.1,
        vessel_draft_m=6.0,
        displacement_t=8420.0,
        speed_knots=[18.0, 20.0],
    )

    assert summary.status == "completed"
    case_dir = next((tmp_path / "projects").iterdir())
    assert (case_dir / "outputs" / "reports" / "report.html").exists()
```

- [ ] **Step 2: Run the integration test to verify it fails**

Run:

```powershell
python -m pytest tests/integration/test_vertical_slice_pipeline.py -v
```

Expected: FAIL because the bootstrap and settings modules do not exist yet.

- [ ] **Step 3: Implement settings, create-case use case, and bootstrap wiring**

```python
# src/bulbopt/infrastructure/config/settings.py
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    project_root: Path
    openfoam_available: bool = False
    default_candidate_count: int = 3
```

```python
# src/bulbopt/application/use_cases/create_case.py
from uuid import uuid4

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.domain.core.models import CaseStatus, OptimizationCase
from bulbopt.storage.project_repository.filesystem_repository import FilesystemProjectRepository


def create_case(command: CreateCaseCommand, repository: FilesystemProjectRepository) -> OptimizationCase:
    case = OptimizationCase.new(case_id=f"case-{uuid4().hex[:8]}", case_name=command.case_name)
    case.source_path = command.source_path
    case.status = CaseStatus.IMPORTED
    repository.create_case(case)
    return case
```

```python
# src/bulbopt/app/bootstrap.py
from pathlib import Path

from bulbopt.application.contracts.models import CreateCaseCommand
from bulbopt.application.use_cases.run_vertical_slice import run_vertical_slice
from bulbopt.infrastructure.config.settings import Settings


def bootstrap_application(project_root: Path) -> dict:
    settings = Settings(project_root=project_root)

    def runner(**kwargs):
        command = CreateCaseCommand(**kwargs)
        return run_vertical_slice(project_root=settings.project_root, command=command)

    return {
        "settings": settings,
        "run_vertical_slice": runner,
    }
```

- [ ] **Step 4: Run the integration test to verify it passes**

Run:

```powershell
python -m pytest tests/integration/test_vertical_slice_pipeline.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit the settings and bootstrap layer**

Run:

```powershell
git add src/bulbopt/infrastructure/config/settings.py src/bulbopt/application/use_cases/create_case.py src/bulbopt/app/bootstrap.py tests/integration/test_vertical_slice_pipeline.py
git commit -m "feat: wire vertical slice through application bootstrap"
```

### Task 7: Add The Desktop Shell And Background Execution Hook

**Files:**
- Create: `src/bulbopt/ui/desktop/case_wizard.py`
- Create: `src/bulbopt/ui/desktop/main_window.py`
- Modify: `src/bulbopt/app/main.py`
- Test: `tests/unit/application/test_ui_smoke.py`

- [ ] **Step 1: Write the failing UI smoke test**

```python
# tests/unit/application/test_ui_smoke.py
from bulbopt.ui.desktop.case_wizard import default_case_payload


def test_default_case_payload_is_stl_first() -> None:
    payload = default_case_payload()

    assert payload["import_format"] == "stl"
    assert payload["optimization_mode"] == "generate_new_bulb"
```

- [ ] **Step 2: Run the UI smoke test to verify it fails**

Run:

```powershell
python -m pytest tests/unit/application/test_ui_smoke.py -v
```

Expected: FAIL because the UI files do not exist yet.

- [ ] **Step 3: Implement the minimal desktop shell**

```python
# src/bulbopt/ui/desktop/case_wizard.py
def default_case_payload() -> dict:
    return {
        "case_name": "new-case",
        "source_path": "",
        "vessel_length_m": 0.0,
        "vessel_beam_m": 0.0,
        "vessel_draft_m": 0.0,
        "displacement_t": 0.0,
        "speed_knots": [18.0],
        "import_format": "stl",
        "optimization_mode": "generate_new_bulb",
    }
```

```python
# src/bulbopt/ui/desktop/main_window.py
from pathlib import Path

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from bulbopt.app.bootstrap import bootstrap_application


class MainWindow(QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.setWindowTitle("BulbOpt Desktop")
        self.services = bootstrap_application(project_root=project_root)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("BulbOpt Desktop"))
        layout.addWidget(QLabel("STL-first vertical slice ready"))
        self.setCentralWidget(central)
```

```python
# src/bulbopt/app/main.py
from pathlib import Path

from PySide6.QtWidgets import QApplication

from bulbopt.ui.desktop.main_window import MainWindow


def build_cli_banner() -> str:
    return "BulbOpt Desktop | STL-first vertical slice"


def run_desktop() -> int:
    app = QApplication([])
    window = MainWindow(project_root=Path("bulbopt_projects"))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_desktop())
```

- [ ] **Step 4: Run the UI smoke test to verify it passes**

Run:

```powershell
python -m pytest tests/unit/application/test_ui_smoke.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit the UI shell**

Run:

```powershell
git add src/bulbopt/ui src/bulbopt/app/main.py tests/unit/application/test_ui_smoke.py
git commit -m "feat: add minimal desktop shell"
```

### Task 8: Strengthen Recovery Metadata And Verify The Full Slice

**Files:**
- Modify: `src/bulbopt/storage/project_repository/filesystem_repository.py`
- Modify: `src/bulbopt/application/use_cases/run_vertical_slice.py`
- Modify: `tests/integration/test_vertical_slice_pipeline.py`

- [ ] **Step 1: Add a failing assertion for recovery metadata**

Append this test to `tests/integration/test_vertical_slice_pipeline.py`:

```python
import json


def test_vertical_slice_writes_resume_metadata(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.stl"
    source_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    app = bootstrap_application(project_root=tmp_path / "projects")
    app["run_vertical_slice"](
        case_name="resume-demo",
        source_path=str(source_path),
        vessel_length_m=142.0,
        vessel_beam_m=19.1,
        vessel_draft_m=6.0,
        displacement_t=8420.0,
        speed_knots=[18.0, 20.0],
    )

    case_dir = next((tmp_path / "projects").iterdir())
    case_payload = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    assert case_payload["status"] == "completed"
    assert case_payload["is_recoverable"] is False
```

- [ ] **Step 2: Run the integration test file to verify the new assertion fails**

Run:

```powershell
python -m pytest tests/integration/test_vertical_slice_pipeline.py -v
```

Expected: FAIL because `run_vertical_slice` does not update `case.json` after completion.

- [ ] **Step 3: Persist final case status and last-stage metadata**

Update `FilesystemProjectRepository` with:

```python
    def save_case(self, case: OptimizationCase) -> None:
        self.json_store.write(self.case_dir(case.case_id) / "case.json", asdict(case))
```

Update `run_vertical_slice` with:

```python
    case.status = CaseStatus.ASSEMBLING_RESULTS
    repository.save_case(case)

    report.build_html_report(
        case_dir,
        {
            "case_name": case.case_name,
            "status": "completed",
            "best_candidate_id": best_candidate["candidate_id"],
            "openfoam_available": False,
            "high_fidelity_used": False,
        },
    )

    case.status = CaseStatus.COMPLETED
    case.is_recoverable = False
    repository.save_case(case)
```

- [ ] **Step 4: Run the full verification suite**

Run:

```powershell
python -m pytest tests/unit tests/integration -v
```

Expected:

```text
all tests passed
```

- [ ] **Step 5: Commit the recovery and verification work**

Run:

```powershell
git add src/bulbopt/storage/project_repository/filesystem_repository.py src/bulbopt/application/use_cases/run_vertical_slice.py tests/integration/test_vertical_slice_pipeline.py
git commit -m "feat: persist final case status for recovery aware runs"
```

## Self-Review

### Spec Coverage

- `System architecture`: covered by repository layout, clean ports, storage, worker, adapters, and UI shell tasks.
- `Case lifecycle and storage`: covered by Task 2, Task 3, and Task 8.
- `Worker and recovery`: covered by Task 4 and Task 8.
- `STL-first vertical slice`: covered by Task 5, Task 6, and Task 7.
- `HTML reporting`: covered by Task 5.
- `OpenFOAM optional`: preserved by stub adapters and settings defaults.

No spec-critical gaps remain for the first vertical slice. `STEP`, `PDF`, `OpenFOAM`, and `high fidelity` are intentionally deferred because the approved scope says they are not required for the initial scaffold.

### Placeholder Scan

No `TBD`, `TODO`, or deferred implementation markers are used inside the task steps. All steps name exact files, commands, and minimal code.

### Type Consistency

The plan consistently uses:

- `CreateCaseCommand`
- `CaseSummary`
- `OptimizationCase`
- `CandidateVariant`
- `FilesystemProjectRepository`
- `LocalWorker`

The same names are reused across tasks, and the storage/update tasks extend the same types rather than introducing alternate names.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-18-bulbopt-desktop-vertical-slice-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

