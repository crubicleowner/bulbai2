from pathlib import Path
import subprocess
import sys

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


def test_default_project_root_is_repo_scoped() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    assert default_project_root() == repo_root / "bulbopt_projects"
