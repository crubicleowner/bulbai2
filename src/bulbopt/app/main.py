from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bulbopt import PACKAGE_NAME, __version__


def build_cli_banner() -> str:
    return f"{PACKAGE_NAME} {__version__} | STL-first vertical slice"


if __name__ == "__main__":
    print(build_cli_banner())
