from __future__ import annotations

import json
from pathlib import Path

from bulbopt.execution.checkpoints.file_checkpoint_store import FileCheckpointStore
from bulbopt.execution.worker.local_worker import LocalWorker
from bulbopt.infrastructure.adapters.openfoam_adapter import OpenFOAMAdapter
from bulbopt.infrastructure.adapters.openfoam_runner import OpenFOAMRunnerAdapter


def test_openfoam_runner_prepends_configured_bin_dir_to_subprocess_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Spec §4.8 real-world path: the solver chain must reach blockMesh.exe
    when the engineer sets ``BULBOPT_OPENFOAM_BIN`` (the portable way to
    drive a MinGW Windows build). The runner must prepend that directory
    to the subprocess PATH even when it is not on the parent shell's PATH.
    """
    import subprocess as subprocess_module

    configured_bin = tmp_path / "fake-foam-bin"
    configured_bin.mkdir()
    # Ensure BULBOPT_OPENFOAM_BIN points to the fake dir.
    monkeypatch.setenv("BULBOPT_OPENFOAM_BIN", str(configured_bin))

    case_dir = tmp_path / "case"
    geometry_path = case_dir / "candidate.stl"
    geometry_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    builder = OpenFOAMAdapter()
    monkeypatch.setattr(builder, "is_available", lambda: True)
    manifest = builder.build_case(
        case_dir,
        best_candidate_id="candidate-path",
        best_candidate_geometry_path=geometry_path,
    )

    runner = OpenFOAMRunnerAdapter()
    monkeypatch.setattr(runner, "is_available", lambda: True)

    observed: list[str] = []

    class _FakeCompletedProcess:
        def __init__(self, args, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.args = args
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(args, **kwargs):
        observed.append(kwargs.get("env", {}).get("PATH", ""))
        return _FakeCompletedProcess(args, 0)

    monkeypatch.setattr(subprocess_module, "run", fake_run)

    runner.run_case(
        case_dir / "working" / "openfoam_case",
        case_manifest=manifest,
        execute=True,
    )

    assert observed, "Expected subprocess.run to be called"
    first_path = observed[0]
    # On Windows the adapter shortens paths, so the long form, the short form
    # (8.3 name) and at minimum the leaf name must appear in the prepended PATH.
    long_form = str(configured_bin)
    leaf = configured_bin.name
    assert (
        long_form in first_path
        or leaf in first_path
        or leaf[:6].upper() in first_path.upper()
    ), f"Expected configured bin dir in subprocess PATH; got: {first_path[:300]}"
    # Must be first entry so MinGW loader resolves before system dirs.
    assert first_path.split(";")[0].lower().split("\\")[-1].startswith(leaf[:6].lower()) or \
           first_path.split(";")[0].upper().split("\\")[-1].startswith(leaf[:6].upper()), \
        f"Expected configured bin dir to be the first PATH entry; got: {first_path[:200]}"


def test_openfoam_runner_executes_solver_chain_when_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Spec §4.8: when OpenFOAM is available and execution is requested, the
    runner must actually invoke the solver chain (blockMesh + snappyHexMesh)
    and record each step's exit code in the run manifest so the report can
    flip ``high_fidelity_used`` to True.
    """
    import subprocess as subprocess_module

    case_dir = tmp_path / "case"
    geometry_path = case_dir / "candidate.stl"
    geometry_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    builder = OpenFOAMAdapter()
    monkeypatch.setattr(builder, "is_available", lambda: True)
    manifest = builder.build_case(
        case_dir,
        best_candidate_id="candidate-42",
        best_candidate_geometry_path=geometry_path,
    )

    runner = OpenFOAMRunnerAdapter()
    monkeypatch.setattr(runner, "is_available", lambda: True)

    invocations: list[dict] = []

    class _FakeCompletedProcess:
        def __init__(self, args, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.args = args
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(args, **kwargs):
        invocations.append({"args": list(args), "cwd": str(kwargs.get("cwd"))})
        return _FakeCompletedProcess(args, 0, stdout="ok\n")

    monkeypatch.setattr(subprocess_module, "run", fake_run)

    result = runner.run_case(
        case_dir / "working" / "openfoam_case",
        case_manifest=manifest,
        execute=True,
    )

    assert result["status"] == "executed_ok"
    assert result["is_recoverable"] is True
    assert result["best_candidate_id"] == "candidate-42"
    assert len(invocations) >= 2, "Expected at least blockMesh + snappyHexMesh"
    assert invocations[0]["args"][0] == "blockMesh"
    assert invocations[1]["args"][0] == "snappyHexMesh"
    executed_steps = result.get("executed_steps", [])
    assert executed_steps, "manifest must record each executed step"
    assert all(step["returncode"] == 0 for step in executed_steps)


def test_openfoam_runner_marks_failed_execution_when_solver_exits_nonzero(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """When any step in the solver chain returns a non-zero exit code, the
    runner must stop, mark the manifest ``executed_failed`` with a reason
    pointing at the failing step, and keep the case recoverable so the user
    can re-run via Resume after fixing the solver environment.
    """
    import subprocess as subprocess_module

    case_dir = tmp_path / "case"
    geometry_path = case_dir / "candidate.stl"
    geometry_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    builder = OpenFOAMAdapter()
    monkeypatch.setattr(builder, "is_available", lambda: True)
    manifest = builder.build_case(
        case_dir,
        best_candidate_id="candidate-99",
        best_candidate_geometry_path=geometry_path,
    )

    runner = OpenFOAMRunnerAdapter()
    monkeypatch.setattr(runner, "is_available", lambda: True)

    class _FakeCompletedProcess:
        def __init__(self, args, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.args = args
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(args, **kwargs):
        if args[0] == "blockMesh":
            return _FakeCompletedProcess(args, 0, stdout="ok\n")
        # snappyHexMesh fails
        return _FakeCompletedProcess(args, 1, stdout="", stderr="boom\n")

    monkeypatch.setattr(subprocess_module, "run", fake_run)

    result = runner.run_case(
        case_dir / "working" / "openfoam_case",
        case_manifest=manifest,
        execute=True,
    )

    assert result["status"] == "executed_failed"
    assert "snappyHexMesh" in result["reason"]
    assert result["is_recoverable"] is True
    assert result["high_fidelity_used"] is False
    assert len(result["executed_steps"]) == 2
    assert result["executed_steps"][0]["returncode"] == 0
    assert result["executed_steps"][1]["returncode"] == 1


def test_openfoam_runner_returns_recoverable_skip_when_solver_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case_dir = tmp_path / "case"
    geometry_path = case_dir / "candidate.stl"
    geometry_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    builder = OpenFOAMAdapter()
    monkeypatch.setattr(builder, "is_available", lambda: False)
    manifest = builder.build_case(
        case_dir,
        best_candidate_id="candidate-7",
        best_candidate_geometry_path=geometry_path,
    )

    runner = OpenFOAMRunnerAdapter()
    monkeypatch.setattr(runner, "is_available", lambda: False)
    result = runner.run_case(case_dir / "working" / "openfoam_case", case_manifest=manifest)

    assert result["status"] == "skipped"
    assert result["reason"] == "openfoam_unavailable"
    assert result["is_recoverable"] is True
    assert (case_dir / "working" / "openfoam_case" / "openfoam_run_manifest.json").exists()


def test_openfoam_runner_can_be_executed_through_local_worker(tmp_path: Path, monkeypatch) -> None:
    case_dir = tmp_path / "case"
    geometry_path = case_dir / "candidate.stl"
    geometry_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_path.write_text("solid demo\nendsolid demo\n", encoding="utf-8")

    builder = OpenFOAMAdapter()
    monkeypatch.setattr(builder, "is_available", lambda: False)
    manifest = builder.build_case(
        case_dir,
        best_candidate_id="candidate-9",
        best_candidate_geometry_path=geometry_path,
    )

    runner = OpenFOAMRunnerAdapter()
    monkeypatch.setattr(runner, "is_available", lambda: False)
    worker = LocalWorker(checkpoint_store=FileCheckpointStore(root_dir=tmp_path / "checkpoints"))

    result = worker.run(
        "case-foam",
        "openfoam-runner",
        lambda: runner.run_case(case_dir / "working" / "openfoam_case", case_manifest=manifest),
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "openfoam_unavailable"
    checkpoint_payload = json.loads(
        (tmp_path / "checkpoints" / "case-foam-openfoam-runner.json").read_text(encoding="utf-8")
    )
    assert checkpoint_payload["status"] == "completed"
    assert checkpoint_payload["result"]["status"] == "skipped"
