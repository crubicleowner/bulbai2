from pathlib import Path
import subprocess
import sys

from bulbopt.app.main import build_cli_banner


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
