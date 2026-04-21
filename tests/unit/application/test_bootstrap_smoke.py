from pathlib import Path
import subprocess
import sys

from bulbopt.app.bootstrap import bootstrap_application
from bulbopt.app.main import build_cli_banner, default_project_root, dispatch_main


def test_build_cli_banner_and_direct_entry_are_consistent() -> None:
    banner = build_cli_banner()
    expected_banner = "BulbOpt Desktop | STL-first vertical slice"

    assert banner == expected_banner

    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "src" / "bulbopt" / "app" / "main.py"
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == expected_banner


def test_dispatch_main_prints_banner_for_direct_script() -> None:
    lines: list[str] = []

    def fake_print(message: str) -> None:
        lines.append(message)

    def fail_run_desktop() -> int:
        raise AssertionError("desktop shell should not start for direct script entry")

    exit_code = dispatch_main(
        run_shell=fail_run_desktop,
        print_banner=fake_print,
        launched_as_module=False,
    )

    assert exit_code == 0
    assert lines == [build_cli_banner()]


def test_dispatch_main_launches_shell_for_module_entry() -> None:
    lines: list[str] = []

    def fake_run_desktop() -> int:
        return 42

    exit_code = dispatch_main(
        run_shell=fake_run_desktop,
        print_banner=lines.append,
        launched_as_module=True,
    )

    assert exit_code == 42
    assert lines == []


def test_default_project_root_prefers_localappdata(monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")

    assert default_project_root() == Path(r"C:\Users\tester\AppData\Local") / "BulbOpt" / "projects"


def test_default_project_root_falls_back_to_home_directory(monkeypatch) -> None:
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr("bulbopt.app.main.Path.home", lambda: Path("/tmp/test-home"))

    assert default_project_root() == Path("/tmp/test-home") / ".bulbopt" / "projects"


def test_bootstrap_application_detects_openfoam_boundary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("bulbopt.app.bootstrap.detect_openfoam_available", lambda: True)

    services = bootstrap_application(project_root=tmp_path / "projects")

    assert services["settings"].openfoam_available is True
