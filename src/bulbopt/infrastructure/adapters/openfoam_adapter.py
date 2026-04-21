from __future__ import annotations

import os
import shutil


class OpenFOAMAdapter:
    """Optional boundary for future high-fidelity CFD integration."""

    EXECUTABLE_CANDIDATES = ("foamRun", "simpleFoam", "interFoam", "blockMesh")

    def is_available(self) -> bool:
        if os.environ.get("WM_PROJECT"):
            return True
        return any(shutil.which(executable) for executable in self.EXECUTABLE_CANDIDATES)

    def boundary_summary(self) -> dict[str, bool | str]:
        return {
            "adapter": "openfoam",
            "available": self.is_available(),
            "used": False,
            "mode": "optional",
        }


def detect_openfoam_available() -> bool:
    return OpenFOAMAdapter().is_available()
