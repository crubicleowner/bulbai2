# BulbOpt Desktop Design Specification

**Date:** 2026-04-18
**Status:** Draft for review
**Product:** `BulbOpt Desktop`
**Scope:** Hybrid MVP, STL-first, HTML-report first, OpenFOAM optional

---

## 1. Purpose

`BulbOpt Desktop` is a modular desktop application for automated generation, optimization, and engineering evaluation of a ship bulbous bow based on a 3D hull model.

The first target is a realistic hybrid MVP:

- desktop UI for engineers and researchers
- Python-based engineering core
- local worker for long-running calculations
- geometry pipeline with repair and bulb generation
- staged candidate evaluation
- report and artifact export

The MVP is intended for:

- single-hull vessels
- pre-sketch and modernization studies
- validation on `DTMB 5415`
- weak or mid-range user machines, including laptops without mandatory GPU

The system must support overnight unattended runs, partial failure tolerance, checkpoint-based recovery, and transparent reporting of model limitations.

---

## 2. Product Positioning

The product is not a pure UI prototype and not a full CFD workstation.

The agreed product direction is a **hybrid MVP**:

- usable desktop application
- real case storage and execution flow
- real geometry processing pipeline
- simplified engineering evaluation in the first vertical slice
- optional integration with heavier engineering tools later

This means:

- `OpenFOAM` is architecturally supported but optional
- `high fidelity` evaluation is not required for the first scaffold
- the first slice must be a real end-to-end workflow, not an empty shell
- the first working slice is `STL-first`
- `STEP` is supported in architecture, but not a blocker for the first executable slice
- `HTML` report is primary in the first slice; `PDF` can follow later

---

## 3. System Architecture

The system shall be implemented as a **modular desktop application with a local worker**.

High-level architecture:

- `Desktop shell` on `PySide6`
- `Application layer` for use-case orchestration
- `Domain core` for engineering entities and rules
- `Local worker` as a separate execution layer
- `Geometry pipeline`
- `Evaluation pipeline`
- `Optimization engine`
- `Reporting/export layer`
- `Infrastructure adapters`
- `Project storage`

Two architectural rules are mandatory:

1. `Local worker` represents a separate execution layer responsible for long-running operations outside the UI thread, task queue management, and checkpoint persistence.
2. All external engineering libraries and solver tools are connected only through the adapter layer; `domain core` must not depend on concrete libraries.

This architecture is considered:

- correct for the engineering problem
- realistic for MVP delivery
- suitable for weak laptops
- extensible toward `OpenFOAM` and surrogate-based evaluation later

---

## 4. Module Boundaries

### 4.1 `ui.desktop`

Responsibilities:

- load hull models
- collect user inputs and case settings
- start and stop workflows
- display geometry, statuses, logs, plots, and results

Must not:

- run heavy engineering calculations
- call external engineering libraries directly

### 4.2 `application.use_cases`

Responsibilities:

- orchestrate product scenarios
- combine domain rules, services, worker jobs, storage, and reporting
- represent business-level user actions

Expected scenarios include:

- `import_hull_case`
- `repair_geometry`
- `detect_bulb_region`
- `generate_bulb_candidates`
- `run_night_optimization`
- `export_results`

This layer works through ports and contracts, not direct library calls.

### 4.3 `application.contracts`

Responsibilities:

- define input commands
- define output DTOs
- define stable request/response formats between UI, use cases, and worker

Examples:

- `ImportHullCommand`
- `RepairGeometryCommand`
- `GenerateCandidatesCommand`
- `RunOptimizationCommand`
- `ExportReportCommand`
- `CaseSummary`
- `CaseStatusView`
- `GeometryQualityReport`
- `CandidateSummary`
- `EvaluationSummary`
- `OptimizationSummary`
- `ReportArtifact`

The system should not pass raw dictionaries between layers as a normal contract mechanism.

### 4.4 `application.services`

This is an optional supporting layer.

Responsibilities:

- coordination helpers
- domain-neutral support services
- reusable orchestration utilities that do not belong in UI or domain

It must not become a general dumping ground for business logic.

### 4.5 `domain.core`

Responsibilities:

- core engineering entities
- invariants
- constraints
- ranking rules
- objective function structure
- case and candidate state models

Expected entities:

- `HullModel`
- `BulbRegion`
- `BulbParameters`
- `OperationalProfile`
- `ConstraintSet`
- `CandidateVariant`
- `EvaluationResult`
- `OptimizationCase`

`domain core` must remain independent from `Trimesh`, `PyMeshFix`, `PyGeM`, `PyVista`, `OpenFOAM`, and any other concrete tool.

### 4.6 `execution.worker`

Responsibilities:

- background execution outside the UI thread
- local queue handling
- progress publication
- checkpoint creation
- failure isolation
- controlled completion states

The worker must support:

- long-running jobs
- recovery from the last completed stage
- per-candidate isolation
- clean propagation of status and errors to the UI

### 4.7 `geometry.pipeline`

Responsibilities:

- import mesh or CAD geometry into a unified internal representation
- run geometry validation
- run repair
- detect the bow region
- detect and confirm the bulb area
- remove or morph the bulb
- generate new bulb candidates
- prepare geometry for downstream evaluation

Core rule:

- `geometry.pipeline` creates and transforms shape

### 4.8 `evaluation.pipeline`

Responsibilities:

- fast filtering of poor candidates
- simplified hydrostatic checks
- simplified or surrogate-based engineering assessment
- optional high-fidelity verification of top candidates

Core rule:

- `evaluation.pipeline` evaluates shape

Evaluation levels:

- `fast screening`
- `mid fidelity`
- `high fidelity`

For MVP:

- `high fidelity` may be unavailable
- lack of `high fidelity` must be visible in the final report

### 4.9 `optimization.engine`

Responsibilities:

- choose which candidate to generate or test next
- rank candidates
- enforce optimization budget
- enforce stop conditions
- work with constraints and objective values

Core rule:

- `optimization.engine` decides which shape to try next

For the first scaffold, the engine may use a heuristic generator/ranker. Integration with `DEAP`, `pygmo`, and `BoTorch` is a later step.

### 4.10 `reporting.export`

Responsibilities:

- build user-facing reports
- produce tables and plots
- export final geometry
- package outputs and artifacts

For the first slice:

- `HTML` is the primary report format
- `PDF` is postponed to a later step

### 4.11 `infrastructure.adapters`

Responsibilities:

- all concrete integrations with external engineering tools
- conversion between internal contracts and library-specific APIs

Planned adapters:

- `Trimesh`
- `PyMeshFix`
- `PyGeM`
- `PyVista`
- optional `OpenFOAM`
- later `DEAP`, `pygmo`, `BoTorch`, and hydrostatic tools

### 4.12 `infrastructure.config`

Responsibilities:

- application settings
- path configuration
- worker limits
- fidelity settings
- time budgets
- retry and recovery policy
- optional tool discovery, including `OpenFOAM`

### 4.13 `storage.filesystem`

Responsibilities:

- low-level file IO
- directory creation
- JSON read/write
- artifact placement
- log file handling

### 4.14 `storage.project_repository`

Responsibilities:

- domain-readable access to cases
- case loading and saving
- artifact pointer management
- checkpoint discovery

`application.use_cases` must work with `ProjectRepository`, not raw paths and JSON files.

---

## 5. Ports and Interfaces

The use-case layer must depend on ports, not concrete adapters.

Initial ports:

- `GeometryService`
- `EvaluationService`
- `OptimizationService`
- `ReportService`
- `ProjectRepository`
- `JobScheduler`
- `CheckpointStore`

This keeps the system stub-friendly and lets the first scaffold work without heavy optional dependencies.

---

## 6. Optimization Case Model

The basic unit of work is `OptimizationCase`.

An `OptimizationCase` represents one hull, one configuration, and one optimization scenario.

It includes:

- source geometry
- physical metadata
- operational profile
- constraints
- execution status
- intermediate engineering artifacts
- candidate results
- exported outputs

The case is divided into five logical data groups:

### 6.1 Source Data

- source `STL` or `STEP`
- scale information
- length, beam, draft, displacement
- water density
- speed range
- operational profile
- optional wave-condition inputs

### 6.2 Case Configuration

- mode: `local_optimize` or `generate_new_bulb`
- total runtime budget
- allowed geometry limits
- enabled fidelity levels
- candidate budget
- optional solver flags

### 6.3 Intermediate Engineering Artifacts

- repaired mesh
- bow-region mask
- bulb-region mask
- intermediate candidate geometries
- geometry summaries
- screening and evaluation outputs

### 6.4 Execution Metadata

- case status
- event log
- candidate failures
- checkpoints
- start and finish timestamps

### 6.5 Outputs

- best geometry
- comparison tables
- plots
- final report
- archived case package

---

## 7. Case Lifecycle

The main case states for MVP are:

- `draft`
- `imported`
- `validated`
- `repairing_geometry`
- `geometry_ready`
- `bulb_region_pending_confirmation`
- `ready_for_optimization`
- `running_fast_screening`
- `running_mid_fidelity`
- `running_high_fidelity`
- `assembling_results`
- `completed`
- `completed_with_warnings`
- `paused`
- `failed`

Recovery is represented by flags and metadata, not by a standalone status:

- `is_recoverable`
- checkpoint references
- last completed stage

This keeps the status model compact while still supporting recovery logic.

---

## 8. Candidate Lifecycle

Candidates must be modeled independently from case state so that one failed candidate does not fail the whole case.

Candidate status examples:

- `generated`
- `geometry_invalid`
- `screened_out`
- `queued_for_evaluation`
- `fast_score_ready`
- `mid_score_ready`
- `high_score_ready`
- `ranked`
- `failed`

Candidate recovery and retry logic is expressed through fields such as:

- `status`
- `error_code`
- `retry_count`
- `can_retry`

---

## 9. File-Based Project Storage

For MVP, project storage shall be file-based rather than database-based.

Rationale:

- easier to debug
- transparent for engineers
- suitable for weak laptops
- convenient for recovery and reproducibility

Suggested case structure:

```text
bulbopt_projects/
  case-2026-04-18-001/
    case.json
    metadata.json
    artifacts_index.json
    candidate_index.json
    evaluation_index.json
    input/
      hull.stl
      hull.step
    working/
      repaired/
      masks/
      candidates/
      evaluation/
      checkpoints/
    outputs/
      geometry/
      reports/
      plots/
      tables/
    logs/
      case.log
      worker.log
```

### 9.1 `case.json`

Contains:

- `schema_version`
- `app_version`
- case id
- status
- created and updated timestamps
- case configuration
- summary metrics
- artifact pointers

### 9.2 `metadata.json`

Contains:

- hull-related physical inputs
- user-supplied vessel parameters
- operational profile
- environment inputs

### 9.3 `artifacts_index.json`

This file is a manifest of important artifacts and their paths.

It prevents UI and reporting layers from guessing where outputs are stored.

### 9.4 Other index files

- `candidate_index.json` for candidate states and references
- `evaluation_index.json` for fidelity-level results
- checkpoint files for worker recovery

---

## 10. Recovery and Failure-Tolerance Rules

The MVP must support resilient overnight execution.

Mandatory rules:

- each major pipeline stage writes a checkpoint
- each candidate is evaluated in isolation
- failure of one candidate does not terminate the entire case
- the case may end as `completed_with_warnings`
- restart must detect the last completed stage
- the application must offer continuation without manual filesystem repair
- unavailable `high fidelity` evaluation is treated as a known limitation, not silent failure

Recovery quality criterion:

After application restart, the system must correctly detect the last completed stage and offer case continuation without manual restoration of the file structure.

---

## 11. User Scenarios for MVP

The MVP covers five main user scenarios.

### 11.1 Import and Prepare Hull

User:

- creates a case
- imports `STL` or `STEP`
- enters required metadata
- starts geometry analysis

System:

- imports geometry
- checks model quality
- proposes repair when needed
- saves the prepared case

### 11.2 Confirm Bulb Region

User:

- opens bow geometry view
- reviews the automatically detected bulb area
- confirms or adjusts it

System:

- detects bow region
- proposes bulb region
- stores the confirmed working region

### 11.3 Generate New Bulb

User:

- selects `generate_new_bulb`
- sets geometry limits
- launches generation

System:

- removes or replaces existing bulb geometry
- creates candidate variants
- validates geometry
- forwards valid candidates for evaluation

### 11.4 Local Optimization of Existing Bulb

User:

- selects `local_optimize`
- constrains allowed shape changes
- starts optimization

System:

- morphs the existing bulb
- produces variations
- rejects invalid geometry
- ranks viable candidates

### 11.5 Overnight Run and Reporting

User:

- sets runtime budget
- selects the operational profile
- starts background execution

System:

- schedules work in the local worker
- runs staged evaluation
- persists checkpoints
- produces best candidate, report, and export package

---

## 12. First Vertical Slice

The first vertical slice is an internal engineering milestone. It is the minimum honest end-to-end proof that the architecture works.

It is not the same as the full MVP product.

Included in the first vertical slice:

- case creation
- `STL` import
- metadata input
- geometry analysis and basic repair
- semi-automatic bulb-region confirmation
- generation of a limited set of candidates
- `fast screening`
- simplified `mid fidelity` evaluation
- ranking
- case persistence
- `HTML` report
- final `STL` export

Not required for the first vertical slice:

- mandatory `STEP` execution path
- mandatory `OpenFOAM`
- mandatory `high fidelity`
- full wave modeling
- full multi-objective optimization
- `PDF` report

Acceptance criteria for the first vertical slice:

1. the system creates and persists a case on disk
2. the system imports `STL`
3. the system accepts required physical and operational metadata
4. the system validates geometry and performs basic repair when needed
5. the system detects the bow region and supports bulb-area confirmation
6. the system generates at least one geometrically valid candidate and at least one evaluated candidate suitable for ranking
7. the system performs `fast` and `mid fidelity` evaluation for at least part of the candidate set
8. the system chooses a best valid candidate according to the configured objective
9. the system generates an `HTML` report with before/after comparison
10. after restart, the application detects the last completed stage and offers continuation
11. the workflow completes on the target machine in a bounded reasonable time without making the system unusable

Practical timing expectation:

- import and preparation should finish in minutes, not indefinitely
- generation and screening should be bounded to tens of minutes in the first slice, not open-ended

---

## 13. MVP Product Boundaries

The MVP is the first usable product, not just an engineering proof.

MVP constraints:

- support only single-hull vessels
- validate primarily on `DTMB 5415`
- focus on bow-region modernization
- use simplified wave treatment
- keep `OpenFOAM` optional
- allow operation without `high fidelity`
- clearly mark outputs as preliminary if only surrogate or simplified evaluation was used

MVP product acceptance criteria:

- the user completes the main workflow without editing files manually
- the UI stays responsive during long runs
- failure of one candidate does not terminate the whole case
- the case can be reopened and continued
- the system produces a reproducible artifact package
- for `DTMB 5415`, the system finds at least one meaningful candidate that is comparable or better according to the selected simplified metric

---

## 14. Reporting Requirements

The report must be engineering-honest and must expose limitations.

The first report must include:

- input model description
- input parameters
- selected optimization mode
- number of candidates considered
- best candidate summary
- comparison tables
- convergence or ranking plots
- before/after visual comparison
- hydrostatic summary where available
- explicit limitation markers

The report must explicitly state:

- whether `high fidelity` was used
- whether `OpenFOAM` was available
- how many candidates were rejected for geometry reasons
- how many candidates failed during execution
- whether the conclusion is preliminary and surrogate-based

---

## 15. Technology Stack

Base stack:

- `Python 3.12+`
- `PySide6`
- `PyVista`
- `Trimesh`
- `PyMeshFix`
- `PyGeM`
- `numpy`
- `scipy`
- `pandas`
- `pytest`
- `jinja2`

Deferred or optional:

- `OpenFOAM`
- `DEAP`
- `pygmo`
- `BoTorch`
- `FreeCAD-Ship`
- `NavalToolbox`
- `weasyprint` for later `PDF` export

---

## 16. Repository Structure

Proposed repository layout:

```text
bulbopt-desktop/
  pyproject.toml
  README.md
  .gitignore
  src/
    bulbopt/
      app/
        main.py
        bootstrap.py
      ui/
        desktop/
          main_window.py
          case_wizard.py
          views/
          widgets/
      application/
        contracts/
        use_cases/
        services/
      domain/
        core/
        rules/
        value_objects/
      execution/
        worker/
        jobs/
        checkpoints/
      geometry/
        pipeline/
        services/
      evaluation/
        pipeline/
        models/
      optimization/
        engine/
        strategies/
      reporting/
        export/
        templates/
      infrastructure/
        adapters/
        config/
        logging/
      storage/
        project_repository/
        filesystem/
  tests/
    unit/
    integration/
    e2e/
  docs/
    superpowers/
      specs/
      plans/
```

This layout enforces:

- clean UI separation
- clean domain boundaries
- adapter-first tool integration
- repository-level support for testing and staged delivery

---

## 17. First Scaffold Scope

The first scaffold must create a working project foundation, not a mock repository.

Included in the scaffold:

- runnable desktop application
- case creation and open flow
- use-case interfaces and contracts
- project repository and filesystem storage
- local worker with queue and checkpoint hooks
- adapter stubs
- one end-to-end workflow from import to report
- test skeleton

Excluded from the scaffold:

- mandatory `STEP` execution path
- complete `OpenFOAM` adapter
- advanced optimization stack
- advanced visual analytics
- plugin system
- installer and updater work

The optimization engine in the scaffold may rely on a simple heuristic generator/ranker.

---

## 18. First End-to-End Workflow in the Scaffold

The first implemented workflow should be:

1. create a case
2. import `STL`
3. persist `case.json` and `metadata.json`
4. validate geometry
5. run basic or stub repair
6. generate a small number of bulb candidates
7. run simplified `fast screening`
8. rank candidates
9. generate `HTML` report
10. store outputs in the case folder

This gives the project a real end-to-end baseline without pretending to deliver full engineering depth on day one.

---

## 19. Non-Goals for the Initial Scaffold

The initial scaffold must avoid:

- premature dependency injection complexity
- universal abstraction for many solvers
- direct UI dependence on external library data models
- mandatory CFD dependence
- pretending that simplified evaluation is full validation

---

## 20. Final Design Summary

The agreed design for `BulbOpt Desktop` is:

- modular desktop application
- `PySide6 + Python`
- local worker as a separate execution layer
- clean `domain core`
- external tools only through adapters
- file-based project storage
- `STL-first`
- `HTML-report first`
- `OpenFOAM optional`
- `high fidelity` optional for the first scaffold
- first slice as a real end-to-end pipeline

This design is:

- architecturally sound
- realistic for MVP delivery
- suitable for weak hardware
- extendable toward surrogate and CFD integration later

