from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Final

_BANNER_SUFFIX: Final[str] = "STL-first vertical slice"


def _package_identity() -> tuple[str, str]:
    try:
        from bulbopt import PACKAGE_NAME, __version__
    except ModuleNotFoundError as exc:
        if exc.name != "bulbopt":
            raise
        package_init = Path(__file__).resolve().parents[1] / "__init__.py"
        spec = spec_from_file_location("_bulbopt_metadata", package_init)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load BulbOpt package metadata")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        PACKAGE_NAME = module.PACKAGE_NAME
        __version__ = module.__version__

    return PACKAGE_NAME, __version__


def build_cli_banner() -> str:
    package_name, version = _package_identity()
    return f"{package_name} {version} | {_BANNER_SUFFIX}"


if __name__ == "__main__":
    print(build_cli_banner())