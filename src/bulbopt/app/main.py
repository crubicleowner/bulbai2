from __future__ import annotations

from pathlib import Path
import sys
from typing import Final

_BANNER_SUFFIX: Final[str] = "STL-first vertical slice"


def _package_identity() -> tuple[str, str]:
    try:
        from bulbopt import PACKAGE_NAME, __version__
    except ModuleNotFoundError as exc:
        if exc.name != "bulbopt":
            raise
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from bulbopt import PACKAGE_NAME, __version__

    return PACKAGE_NAME, __version__


def build_cli_banner() -> str:
    package_name, version = _package_identity()
    return f"{package_name} {version} | {_BANNER_SUFFIX}"


if __name__ == "__main__":
    print(build_cli_banner())