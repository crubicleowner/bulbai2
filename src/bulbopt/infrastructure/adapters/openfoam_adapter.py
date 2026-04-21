from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys


def _shorten_path(path: str) -> str:
    """Return Windows 8.3 short path when available (fixes non-ASCII paths that
    break MinGW dynamic linker lookups). On non-Windows or when conversion
    fails, returns the input unchanged.
    """
    if sys.platform != "win32":
        return path
    try:
        import ctypes

        get_short = ctypes.windll.kernel32.GetShortPathNameW  # type: ignore[attr-defined]
        get_short.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        get_short.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32768)
        written = get_short(str(path), buffer, len(buffer))
        if written and buffer.value:
            return buffer.value
    except Exception:
        pass
    return str(path)


def _configured_bin_dir() -> str | None:
    """Return the explicit OpenFOAM bin directory, if one is configured.

    Checked in order:
      1. ``BULBOPT_OPENFOAM_BIN`` (preferred, explicit)
      2. ``FOAM_APPBIN`` (set by the official OpenFOAM env scripts)
      3. ``WM_PROJECT_DIR`` joined with the platform-specific bin suffix
    """
    explicit = os.environ.get("BULBOPT_OPENFOAM_BIN")
    if explicit and Path(explicit).exists():
        return explicit

    foam_appbin = os.environ.get("FOAM_APPBIN")
    if foam_appbin and Path(foam_appbin).exists():
        return foam_appbin

    project_dir = os.environ.get("WM_PROJECT_DIR")
    if project_dir:
        for candidate_suffix in (
            Path("platforms") / "win64MingwDPInt32Opt" / "bin",
            Path("platforms") / "linux64GccDPInt32Opt" / "bin",
        ):
            candidate = Path(project_dir) / candidate_suffix
            if candidate.exists():
                return str(candidate)
    return None


class OpenFOAMAdapter:
    """Optional boundary for future high-fidelity CFD integration."""

    EXECUTABLE_CANDIDATES = ("foamRun", "simpleFoam", "interFoam", "blockMesh")

    def is_available(self) -> bool:
        if os.environ.get("WM_PROJECT"):
            return True
        if _configured_bin_dir():
            return True
        return any(shutil.which(executable) for executable in self.EXECUTABLE_CANDIDATES)

    def boundary_summary(self) -> dict[str, bool | str]:
        return {
            "adapter": "openfoam",
            "available": self.is_available(),
            "used": False,
            "mode": "optional",
        }

    def build_case(
        self,
        case_dir: Path,
        *,
        best_candidate_id: str,
        best_candidate_geometry_path: Path,
    ) -> dict[str, bool | str]:
        openfoam_case_dir = case_dir / "working" / "openfoam_case"
        tri_surface_dir = openfoam_case_dir / "constant" / "triSurface"
        system_dir = openfoam_case_dir / "system"
        constant_dir = openfoam_case_dir / "constant"
        tri_surface_dir.mkdir(parents=True, exist_ok=True)
        system_dir.mkdir(parents=True, exist_ok=True)
        constant_dir.mkdir(parents=True, exist_ok=True)

        target_stl = tri_surface_dir / "best_candidate.stl"
        shutil.copyfile(best_candidate_geometry_path, target_stl)

        (system_dir / "controlDict").write_text(self._control_dict(), encoding="utf-8")
        (system_dir / "blockMeshDict").write_text(self._block_mesh_dict(), encoding="utf-8")
        (system_dir / "snappyHexMeshDict").write_text(self._snappy_hex_mesh_dict(), encoding="utf-8")
        (system_dir / "fvSchemes").write_text(self._fv_schemes(), encoding="utf-8")
        (system_dir / "fvSolution").write_text(self._fv_solution(), encoding="utf-8")
        (constant_dir / "transportProperties").write_text(self._transport_properties(), encoding="utf-8")

        manifest = {
            "adapter": "openfoam",
            "available": self.is_available(),
            "used": False,
            "mode": "optional",
            "case_built": True,
            "best_candidate_id": best_candidate_id,
            "case_directory": str(openfoam_case_dir),
            "geometry_path": str(target_stl),
            "mesh_templates": ["blockMeshDict", "snappyHexMeshDict"],
        }
        (openfoam_case_dir / "openfoam_case_manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        return manifest

    def _control_dict(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       dictionary;\n"
            "    object      controlDict;\n"
            "}\n"
            "application     interFoam;\n"
            "startFrom       latestTime;\n"
            "stopAt          endTime;\n"
            "endTime         200;\n"
            "deltaT          0.5;\n"
        )

    def _fv_schemes(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       dictionary;\n"
            "    object      fvSchemes;\n"
            "}\n"
            "ddtSchemes\n"
            "{\n"
            "    default         Euler;\n"
            "}\n"
        )

    def _block_mesh_dict(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       dictionary;\n"
            "    object      blockMeshDict;\n"
            "}\n"
            "convertToMeters 1.0;\n"
            "vertices\n"
            "(\n"
            "    (-12 -6 -6)\n"
            "    ( 24 -6 -6)\n"
            "    ( 24  6 -6)\n"
            "    (-12  6 -6)\n"
            "    (-12 -6  6)\n"
            "    ( 24 -6  6)\n"
            "    ( 24  6  6)\n"
            "    (-12  6  6)\n"
            ");\n"
            "blocks\n"
            "(\n"
            "    hex (0 1 2 3 4 5 6 7) (40 20 20) simpleGrading (1 1 1)\n"
            ");\n"
        )

    def _snappy_hex_mesh_dict(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       dictionary;\n"
            "    object      snappyHexMeshDict;\n"
            "}\n"
            "castellatedMesh true;\n"
            "snap            true;\n"
            "addLayers       false;\n"
            "geometry\n"
            "{\n"
            "    best_candidate.stl\n"
            "    {\n"
            "        type triSurfaceMesh;\n"
            "        name hull;\n"
            "    }\n"
            "}\n"
        )

    def _fv_solution(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       dictionary;\n"
            "    object      fvSolution;\n"
            "}\n"
            "solvers\n"
            "{\n"
            "    p_rgh\n"
            "    {\n"
            "        solver          PCG;\n"
            "    }\n"
            "}\n"
        )

    def _transport_properties(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       dictionary;\n"
            "    object      transportProperties;\n"
            "}\n"
            "transportModel  Newtonian;\n"
            "nu              1e-06;\n"
        )


def detect_openfoam_available() -> bool:
    return OpenFOAMAdapter().is_available()
