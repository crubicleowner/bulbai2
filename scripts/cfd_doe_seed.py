"""Seed the BulbOpt history store with a Latin hypercube DOE of real CFD runs.

Audit 2026-04-26 fix: the analytic mid-gate proxy ``(beam*draft)/axial``
*anti-correlates* with simpleFoam Cd, so the GP surrogate can only
become useful once we have a small bootstrap of real (Kracht, Cd) pairs.
This script deforms the repaired baseline mesh by a Latin hypercube
sample of Kracht vectors, runs each through the OpenFOAM solver chain,
parses Cd from ``forceCoeffs/0/coefficient.dat``, and appends every
result to the project's ``HistoryStore`` with ``backend="simple_foam"``.

Once the history accumulates ``>=12`` ``simple_foam`` rows, the existing
GP-mid-gate path activates automatically (see
``run_night_optimization``).

Usage::

    set BULBOPT_OPENFOAM_BIN=C:/Users/.../OpenFOAM-v2512/.../bin
    python scripts/cfd_doe_seed.py \
        --case-name doe_2026_04_26 \
        --root C:/Users/.../bulbopt_projects \
        --n 30 \
        --bounds tightened

The script is intentionally **defensive on failure** — a single failed
case does not abort the sweep. ``cd`` is recorded as ``None`` in the
per-case manifest and that vector is *not* appended to the history
store (we never want to train the GP on ``None``).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import trimesh

from bulbopt.infrastructure.adapters.force_coeffs_parser import (
    ForceCoeffsNotFoundError,
    parse_drag_coefficient_dat,
)
from bulbopt.infrastructure.adapters.openfoam_adapter import OpenFOAMAdapter
from bulbopt.infrastructure.adapters.openfoam_runner import OpenFOAMRunnerAdapter
from bulbopt.infrastructure.adapters.stub_geometry import StubGeometryAdapter
from bulbopt.optimization.doe.latin_hypercube import latin_hypercube_sample
from bulbopt.optimization.learning.history_store import (
    HistoryStore,
    default_history_path,
)
from bulbopt.optimization.parametric.ffd_deformer import BulbFFDDeformer
from bulbopt.optimization.parametric.kracht_space import (
    KRACHT_PARAMETER_NAMES,
    KrachtDesignSpace,
    KrachtVector,
)


def _resolve_design_space(bounds_choice: str) -> KrachtDesignSpace:
    """Build the KrachtDesignSpace requested by ``--bounds``.

    Module C may or may not have shipped ``KrachtDesignSpace.tightened()``
    yet; if it's missing we degrade gracefully to the default space and
    print a clear note.
    """
    if bounds_choice == "full":
        return KrachtDesignSpace()
    if bounds_choice == "tightened":
        if hasattr(KrachtDesignSpace, "tightened"):
            return KrachtDesignSpace.tightened()
        print(
            "  NOTE: KrachtDesignSpace.tightened() not available yet — "
            "falling back to default bounds.",
            file=sys.stderr,
        )
        return KrachtDesignSpace()
    raise ValueError(f"Unknown --bounds: {bounds_choice!r}")


def _build_baseline(
    *,
    case_dir: Path,
    source_stl: Path,
) -> tuple[trimesh.Trimesh, dict]:
    """Run ``prepare_geometry`` on the case dir and return (mesh, region)."""
    case_dir.mkdir(parents=True, exist_ok=True)
    # StubGeometryAdapter.prepare_geometry writes to <case_dir>/input/,
    # <case_dir>/working/repaired/, and reads/writes <case_dir>/artifacts_index.json.
    # None of those are created by the adapter itself. Set up the skeleton first.
    (case_dir / "input").mkdir(parents=True, exist_ok=True)
    (case_dir / "working" / "repaired").mkdir(parents=True, exist_ok=True)
    artifacts_path = case_dir / "artifacts_index.json"
    if not artifacts_path.exists():
        artifacts_path.write_text("{}", encoding="utf-8")
    geometry = StubGeometryAdapter()
    analysis = geometry.prepare_geometry(case_dir, source_stl)
    repaired_path = case_dir / "working" / "repaired" / "repaired.stl"
    mesh = trimesh.load(repaired_path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty:
        raise RuntimeError(f"Failed to load repaired mesh from {repaired_path}")
    return mesh, analysis["bulb_region"]


def _run_simple_foam_for_vector(
    *,
    label: str,
    vector: KrachtVector,
    baseline_mesh: trimesh.Trimesh,
    region: dict,
    deformer: BulbFFDDeformer,
    builder: OpenFOAMAdapter,
    runner: OpenFOAMRunnerAdapter,
    work_root: Path,
    timeout_seconds: int,
) -> dict:
    """Build + execute one OpenFOAM case for a Kracht vector. Returns a manifest dict.

    Defensive: any exception inside the deform / build / run stages is
    captured and surfaced as ``status="failed"`` with ``cd=None``.
    """
    case_dir = work_root / label
    if case_dir.exists():
        shutil.rmtree(case_dir, ignore_errors=True)
    case_dir.mkdir(parents=True, exist_ok=True)

    deformed_path = case_dir / "deformed.stl"
    of_case_dir = case_dir / "working" / "openfoam_case"

    manifest: dict = {
        "label": label,
        "vector": dict(vector.values),
        "cd": None,
        "status": "started",
        "reason": None,
        "openfoam_case_dir": str(of_case_dir),
    }

    try:
        deformed = deformer.deform(baseline_mesh, region, vector)
        deformed_path.write_bytes(trimesh.exchange.stl.export_stl(deformed))

        case_manifest = builder.build_case(
            case_dir=case_dir,
            best_candidate_id=label,
            best_candidate_geometry_path=deformed_path,
        )
        run_manifest = runner.run_case(
            of_case_dir,
            case_manifest=case_manifest,
            execute=True,
            timeout_seconds=timeout_seconds,
        )

        runner_status = run_manifest.get("status") or run_manifest.get("runner_status")
        manifest["runner_status"] = runner_status
        manifest["runner_reason"] = (
            run_manifest.get("reason") or run_manifest.get("runner_reason")
        )

        if runner_status != "executed_ok":
            manifest["status"] = "failed"
            manifest["reason"] = manifest["runner_reason"] or "solver_chain_failed"
            return manifest

        cd_value = _read_force_coeffs_cd(of_case_dir)
        if cd_value is None:
            manifest["status"] = "failed"
            manifest["reason"] = "force_coeffs_unavailable"
            return manifest

        manifest["cd"] = float(cd_value)
        manifest["status"] = "succeeded"
        return manifest

    except Exception as exc:  # pragma: no cover - defensive logging path
        manifest["status"] = "failed"
        manifest["reason"] = f"{type(exc).__name__}: {exc}"
        manifest["traceback"] = traceback.format_exc()
        return manifest


def _read_force_coeffs_cd(of_case_dir: Path) -> Optional[float]:
    """Locate ``forceCoeffs/0/coefficient.dat`` and return its final Cd, if any.

    Mirrors :func:`bulbopt.infrastructure.adapters.simple_foam_gate._read_force_coeffs`
    but trimmed to just the ``final_cd`` lookup so the script depends on
    the public parser only.
    """
    post_root = of_case_dir / "postProcessing"
    if not post_root.exists():
        return None
    candidate_roots = [post_root / "forceCoeffs", post_root / "forces"]
    forces_root = next((c for c in candidate_roots if c.exists()), None)
    if forces_root is None:
        return None
    subdirs = [p for p in forces_root.iterdir() if p.is_dir()]
    if not subdirs:
        return None
    latest = max(subdirs, key=lambda p: p.stat().st_mtime)
    dat_path = next(
        (
            latest / filename
            for filename in ("forceCoeffs.dat", "coefficient.dat")
            if (latest / filename).exists()
        ),
        latest / "coefficient.dat",
    )
    try:
        report = parse_drag_coefficient_dat(dat_path)
    except (ForceCoeffsNotFoundError, ValueError):
        return None
    return float(report["final_cd"])


def _run_baseline_cd(
    *,
    baseline_mesh: trimesh.Trimesh,
    builder: OpenFOAMAdapter,
    runner: OpenFOAMRunnerAdapter,
    work_root: Path,
    source_stl: Path,
    timeout_seconds: int,
) -> Optional[float]:
    """Run the undeformed (repaired) baseline through OpenFOAM. Returns Cd or None."""
    case_dir = work_root / "baseline"
    if case_dir.exists():
        shutil.rmtree(case_dir, ignore_errors=True)
    case_dir.mkdir(parents=True, exist_ok=True)
    deformed_path = case_dir / "baseline.stl"
    deformed_path.write_bytes(trimesh.exchange.stl.export_stl(baseline_mesh))
    of_case_dir = case_dir / "working" / "openfoam_case"
    try:
        case_manifest = builder.build_case(
            case_dir=case_dir,
            best_candidate_id="baseline",
            best_candidate_geometry_path=deformed_path,
        )
        run_manifest = runner.run_case(
            of_case_dir,
            case_manifest=case_manifest,
            execute=True,
            timeout_seconds=timeout_seconds,
        )
        if (
            run_manifest.get("status") != "executed_ok"
            and run_manifest.get("runner_status") != "executed_ok"
        ):
            return None
        return _read_force_coeffs_cd(of_case_dir)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  WARN: baseline CFD failed: {exc}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Latin hypercube DOE of real OpenFOAM Cd evaluations and "
            "seed the GP surrogate via the BulbOpt history store."
        )
    )
    parser.add_argument("--n", type=int, default=30, help="Number of LHS samples (default 30)")
    parser.add_argument(
        "--bounds",
        choices=("tightened", "full"),
        default="tightened",
        help="Use tightened (Module C) or full default Kracht bounds (default tightened)",
    )
    parser.add_argument(
        "--case-name",
        required=True,
        help="Logical case-name; the script writes under <root>/<case-name>/",
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Project root containing the seed run (a sibling of normal cases)",
    )
    parser.add_argument(
        "--source-stl",
        default=str(REPO_ROOT / "docs" / "base_hull.stl"),
        help="Source STL to load and repair (default docs/base_hull.stl)",
    )
    parser.add_argument(
        "--history-path",
        default=str(default_history_path()),
        help="Path to the history.jsonl store (default ~/.bulbopt/history.jsonl)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-case OpenFOAM solver-chain timeout in seconds (default 600)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed for LHS sampling (default 0)",
    )
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip the baseline CFD run (useful for resuming a partial sweep)",
    )
    args = parser.parse_args(argv)

    if not os.environ.get("BULBOPT_OPENFOAM_BIN"):
        print(
            "BULBOPT_OPENFOAM_BIN is not set. Point it at the bin/ directory of "
            "your OpenFOAM-v2512 install before running this script. Aborting.",
            file=sys.stderr,
        )
        return 2

    source_stl = Path(args.source_stl).resolve()
    if not source_stl.is_file():
        print(f"Source STL not found: {source_stl}", file=sys.stderr)
        return 2

    project_root = Path(args.root).resolve()
    case_dir = project_root / args.case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    doe_results_dir = case_dir / "doe_results"
    doe_results_dir.mkdir(parents=True, exist_ok=True)
    work_root = case_dir / "working" / "doe"
    work_root.mkdir(parents=True, exist_ok=True)

    history_path = Path(args.history_path).resolve()
    history_store = HistoryStore(path=history_path)

    print(f"Loading + repairing baseline from {source_stl}")
    baseline_mesh, region = _build_baseline(case_dir=case_dir, source_stl=source_stl)

    design_space = _resolve_design_space(args.bounds)
    samples = latin_hypercube_sample(args.n, design_space, seed=args.seed)
    print(
        f"Generated {len(samples)} Latin hypercube samples "
        f"(bounds={args.bounds!r}, seed={args.seed})"
    )

    builder = OpenFOAMAdapter()
    runner = OpenFOAMRunnerAdapter()
    deformer = BulbFFDDeformer()

    start_time = time.monotonic()

    baseline_cd: Optional[float] = None
    if not args.skip_baseline:
        print("== Running baseline (undeformed) through OpenFOAM ==")
        baseline_cd = _run_baseline_cd(
            baseline_mesh=baseline_mesh,
            builder=builder,
            runner=runner,
            work_root=work_root,
            source_stl=source_stl,
            timeout_seconds=args.timeout,
        )
        print(f"  baseline Cd = {baseline_cd}")

    cd_values: list[float] = []
    n_succeeded = 0
    n_failed = 0

    for index, vector in enumerate(samples, start=1):
        label = f"sample_{index:03d}"
        print(f"== {label} ({index}/{len(samples)}) ==")
        result = _run_simple_foam_for_vector(
            label=label,
            vector=vector,
            baseline_mesh=baseline_mesh,
            region=region,
            deformer=deformer,
            builder=builder,
            runner=runner,
            work_root=work_root,
            timeout_seconds=args.timeout,
        )
        # Persist per-case manifest immediately so a crash mid-sweep does
        # not lose evidence.
        manifest_path = doe_results_dir / f"{label}.json"
        manifest_path.write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )

        cd = result.get("cd")
        if result["status"] == "succeeded" and cd is not None:
            history_store.record(vector, cd=float(cd), backend="simple_foam")
            cd_values.append(float(cd))
            n_succeeded += 1
            print(f"  Cd = {cd:.4f}  (recorded in {history_path})")
        else:
            n_failed += 1
            print(
                f"  FAILED: status={result['status']!r} reason={result.get('reason')!r}"
            )

    total_seconds = time.monotonic() - start_time

    summary = {
        "n": int(args.n),
        "n_succeeded": int(n_succeeded),
        "n_failed": int(n_failed),
        "baseline_cd": float(baseline_cd) if baseline_cd is not None else None,
        "min_cd": float(min(cd_values)) if cd_values else None,
        "max_cd": float(max(cd_values)) if cd_values else None,
        "mean_cd": float(statistics.fmean(cd_values)) if cd_values else None,
        "stdev_cd": (
            float(statistics.stdev(cd_values)) if len(cd_values) >= 2 else None
        ),
        "history_path": str(history_path),
        "total_seconds": float(total_seconds),
        "bounds": args.bounds,
        "seed": int(args.seed),
        "source_stl": str(source_stl),
    }
    summary_path = case_dir / "seed_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print()
    print("=" * 78)
    print(f"DOE seed sweep complete in {total_seconds:.1f}s")
    print(f"  succeeded: {n_succeeded}/{args.n}")
    print(f"  failed:    {n_failed}/{args.n}")
    if baseline_cd is not None:
        print(f"  baseline Cd: {baseline_cd:.4f}")
    if cd_values:
        print(
            f"  Cd: min={min(cd_values):.4f} mean={statistics.fmean(cd_values):.4f} "
            f"max={max(cd_values):.4f}"
        )
    print(f"  history file: {history_path}")
    print(f"  summary: {summary_path}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
