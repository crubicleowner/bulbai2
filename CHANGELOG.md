# Changelog

All notable changes to `BulbOpt Desktop` are tracked here, organized by the
vertical-slice milestone and spec section they deliver against. Dates are in
ISO-8601. Commit subjects match `git log --oneline` so entries map one-to-one
to the history on `feature/vertical-slice`.

## First vertical slice — unreleased

Second wave (on top of the hybrid MVP scaffold). 16 commits, 92 tests passing.

### Added — engineering pipeline

- `feat: wire LocalWorker into vertical slice pipeline` — every stage
  (`prepare_geometry`, `generate_candidates`, `evaluate_candidates`,
  `rank_candidates`, `openfoam_build_case`, `openfoam_run_case`,
  `build_html_report`, `export_case_package`) now flows through
  `LocalWorker.run_strict`, producing per-stage checkpoints in
  `working/checkpoints/`. Spec §3.
- `feat: repair non-watertight meshes via PyMeshFix in stub geometry` —
  real `pymeshfix.MeshFix.repair()` replaces the byte-copy stub; graceful
  fallback when repair is impossible (degenerate input) preserves the
  original bytes and flags `repair_status=failed` so the report is
  engineering-honest. Spec §4.7, §12 criterion 4.
- `feat: support local_optimize mode for constrained bulb refinement` —
  `optimization_mode="local_optimize"` uses strictly smaller deformation
  amplitudes than `generate_new_bulb` so the engineer gets local refinement
  of an existing bulb. Spec §11.4.
- `feat: allow engineer to adjust auto-detected bulb region` —
  `CreateCaseCommand.bulb_region_axis_min_override` /
  `_axis_max_override` thread through to `prepare_geometry`; analysis
  preserves both auto-detected and user-confirmed values with a
  `confirmation_source` flag. Spec §11.2.
- `feat: add Detect Bulb Region preview button for spec §11.2 review step` —
  pure `detect_bulb_region(source_path)` returns the preview without
  writing artifacts; desktop shell gains a button + preview label so the
  engineer can review before committing.
- `feat: execute OpenFOAM solver chain when available` —
  `OpenFOAMRunnerAdapter.run_case(execute=True)` subprocesses `blockMesh` +
  `snappyHexMesh -overwrite` when the solver is on `PATH`, records
  per-step exit codes + stdout/stderr tails, flips `high_fidelity_used`
  to True on success, keeps the case recoverable on failure. Spec §4.8.

### Added — persistence, recovery, CLI

- `feat: surface case history in desktop shell for spec §10 resume` —
  `FilesystemProjectRepository.list_cases()` + bootstrap wiring + desktop
  "Previous cases" panel with recoverable-count indicator.
- `feat: resume vertical slice from checkpoints` —
  `FileCheckpointStore.load_completed_result`, `LocalWorker.run_strict
  (resume=True)`, `repository.load_case` / `load_create_case_command`, and
  new `resume_vertical_slice(project_root, case_id)` use case. A
  mid-pipeline failure can be re-attempted without re-entering metadata
  or repeating completed stages. Spec §10.
- `feat: wire Resume button into desktop history panel` — enabled only
  for `is_recoverable=True` entries; refreshes history after a run.
- `feat: archive each completed case as a portable zip package` —
  `CasePackageExporter` writes `outputs/packages/<case-id>.zip` skipping
  runtime checkpoints by default; recorded in `artifacts_index`; UI has
  an "Open Case Package" button. Spec §6.5.
- `feat: add per-stage timing observability for the vertical slice` —
  `LocalWorker` captures `elapsed_seconds` around each job; pipeline
  aggregates into `case.summary_metrics["timing"]` (per-stage rows,
  total, slowest_stage); report renders a Stage timing table.
- `feat: write JSONL per-stage case log for observability` —
  `CaseLogger` writes `logs/case.log` with timestamped JSONL entries for
  every stage transition and pipeline bracket markers. Spec §9.
- `feat: add headless CLI for overnight / SSH / CI runs` —
  `python -m bulbopt.app.main run|list|resume`, argparse subcommands,
  exit 0 / 1 / 2. Spec §1.

### Added — reporting

- `feat: surface geometry repair summary in HTML report` — new "Geometry
  repair" section: repair_status, watertight before/after, V/F deltas.
  Spec §14.
- `feat: add before/after comparison table to HTML report` — baseline vs
  best candidate table with axial/beam/draft/surface metrics and
  percentage deltas. Spec §14.

### Fixed

- `fix: restore docs/base_hull.stl demo fixture` — the 6.2 MB demo STL
  existed on `main` but was never propagated to `feature/vertical-slice`,
  causing 3 UI smoke tests to fail on `discover_demo_source_path`.
  Restored from `main`; suite went from 46/49 to 49/49.

### Docs

- `docs: rewrite README as engineer onboarding and CLI reference` —
  stub README replaced with feature checklist, install, CLI reference,
  case folder layout, pipeline stage overview, and module boundaries.

## Baseline — prior to this work

See commits before `b3c87d6`. The scaffold delivered case creation,
file-based storage, stub geometry/evaluation/optimization adapters,
an HTML template, and a minimal PySide6 shell (~45 commits on the
feature branch).
