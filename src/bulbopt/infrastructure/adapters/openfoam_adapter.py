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
        zero_dir = openfoam_case_dir / "0"
        tri_surface_dir.mkdir(parents=True, exist_ok=True)
        system_dir.mkdir(parents=True, exist_ok=True)
        constant_dir.mkdir(parents=True, exist_ok=True)
        zero_dir.mkdir(parents=True, exist_ok=True)

        target_stl = tri_surface_dir / "best_candidate.stl"
        shutil.copyfile(best_candidate_geometry_path, target_stl)

        (system_dir / "controlDict").write_text(self._control_dict(), encoding="utf-8")
        (system_dir / "blockMeshDict").write_text(self._block_mesh_dict(), encoding="utf-8")
        (system_dir / "snappyHexMeshDict").write_text(self._snappy_hex_mesh_dict(), encoding="utf-8")
        (system_dir / "fvSchemes").write_text(self._fv_schemes(), encoding="utf-8")
        (system_dir / "fvSolution").write_text(self._fv_solution(), encoding="utf-8")
        (constant_dir / "transportProperties").write_text(self._transport_properties(), encoding="utf-8")
        (constant_dir / "turbulenceProperties").write_text(self._turbulence_properties(), encoding="utf-8")
        # Initial fields for simpleFoam (k-omega SST).
        (zero_dir / "U").write_text(self._initial_U(), encoding="utf-8")
        (zero_dir / "p").write_text(self._initial_p(), encoding="utf-8")
        (zero_dir / "k").write_text(self._initial_k(), encoding="utf-8")
        (zero_dir / "omega").write_text(self._initial_omega(), encoding="utf-8")
        (zero_dir / "nut").write_text(self._initial_nut(), encoding="utf-8")

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
            "application         simpleFoam;\n"
            "startFrom           startTime;\n"
            "startTime           0;\n"
            "stopAt              endTime;\n"
            "endTime             200;\n"
            "deltaT              1;\n"
            "writeControl        timeStep;\n"
            "writeInterval       100;\n"
            "purgeWrite          2;\n"
            "writeFormat         ascii;\n"
            "writePrecision      10;\n"
            "writeCompression    off;\n"
            "timeFormat          general;\n"
            "timePrecision       6;\n"
            "runTimeModifiable   false;\n"
            "\n"
            "functions\n"
            "{\n"
            "    forceCoeffs\n"
            "    {\n"
            "        type            forceCoeffs;\n"
            "        libs            (forces);\n"
            "        writeControl    timeStep;\n"
            "        writeInterval   10;\n"
            "        patches         (hull);\n"
            "        rho             rhoInf;\n"
            "        rhoInf          1000;\n"
            "        liftDir         (0 0 1);\n"
            "        dragDir         (1 0 0);\n"
            "        CofR            (0 0 0);\n"
            "        pitchAxis       (0 1 0);\n"
            "        magUInf         5.0;\n"
            "        lRef            10;\n"
            "        Aref            10;\n"
            "    }\n"
            "}\n"
        )

    def _turbulence_properties(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       dictionary;\n"
            "    object      turbulenceProperties;\n"
            "}\n"
            "simulationType  RAS;\n"
            "RAS\n"
            "{\n"
            "    RASModel        kOmegaSST;\n"
            "    turbulence      on;\n"
            "    printCoeffs     on;\n"
            "}\n"
        )

    def _initial_U(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       volVectorField;\n"
            "    object      U;\n"
            "}\n"
            "dimensions      [0 1 -1 0 0 0 0];\n"
            "internalField   uniform (5 0 0);\n"
            "boundaryField\n"
            "{\n"
            "    hull    { type fixedValue; value uniform (0 0 0); }\n"
            "    \".*\"   { type fixedValue; value uniform (5 0 0); }\n"
            "}\n"
        )

    def _initial_p(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       volScalarField;\n"
            "    object      p;\n"
            "}\n"
            "dimensions      [0 2 -2 0 0 0 0];\n"
            "internalField   uniform 0;\n"
            "boundaryField\n"
            "{\n"
            "    hull    { type zeroGradient; }\n"
            "    \".*\"   { type fixedValue; value uniform 0; }\n"
            "}\n"
        )

    def _initial_k(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       volScalarField;\n"
            "    object      k;\n"
            "}\n"
            "dimensions      [0 2 -2 0 0 0 0];\n"
            "internalField   uniform 0.375;\n"
            "boundaryField\n"
            "{\n"
            "    hull    { type kqRWallFunction; value uniform 0.375; }\n"
            "    \".*\"   { type fixedValue; value uniform 0.375; }\n"
            "}\n"
        )

    def _initial_omega(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       volScalarField;\n"
            "    object      omega;\n"
            "}\n"
            "dimensions      [0 0 -1 0 0 0 0];\n"
            "internalField   uniform 3.0;\n"
            "boundaryField\n"
            "{\n"
            "    hull    { type omegaWallFunction; value uniform 3.0; }\n"
            "    \".*\"   { type fixedValue; value uniform 3.0; }\n"
            "}\n"
        )

    def _initial_nut(self) -> str:
        return (
            "FoamFile\n"
            "{\n"
            "    version     2.0;\n"
            "    format      ascii;\n"
            "    class       volScalarField;\n"
            "    object      nut;\n"
            "}\n"
            "dimensions      [0 2 -1 0 0 0 0];\n"
            "internalField   uniform 0;\n"
            "boundaryField\n"
            "{\n"
            "    hull    { type nutkWallFunction; value uniform 0; }\n"
            "    \".*\"   { type calculated; value uniform 0; }\n"
            "}\n"
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
            "ddtSchemes        { default         steadyState; }\n"
            "gradSchemes       { default         Gauss linear; }\n"
            "divSchemes\n"
            "{\n"
            "    default         none;\n"
            "    div(phi,U)      bounded Gauss linearUpwind grad(U);\n"
            "    div(phi,k)      bounded Gauss limitedLinear 1;\n"
            "    div(phi,omega)  bounded Gauss limitedLinear 1;\n"
            "    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n"
            "}\n"
            "laplacianSchemes  { default         Gauss linear corrected; }\n"
            "interpolationSchemes { default      linear; }\n"
            "snGradSchemes     { default         corrected; }\n"
            "wallDist          { method          meshWave; }\n"
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
            "scale 1.0;\n"
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
            "castellatedMeshControls\n"
            "{\n"
            "    maxLocalCells       1000000;\n"
            "    maxGlobalCells      4000000;\n"
            "    minRefinementCells  0;\n"
            "    maxLoadUnbalance    0.10;\n"
            "    nCellsBetweenLevels 3;\n"
            "    features            ();\n"
            "    refinementSurfaces\n"
            "    {\n"
            "        hull\n"
            "        {\n"
            "            level (2 3);\n"
            "        }\n"
            "    }\n"
            "    resolveFeatureAngle 30;\n"
            "    refinementRegions   {}\n"
            "    locationInMesh      (0 0 3);\n"
            "    allowFreeStandingZoneFaces true;\n"
            "}\n"
            "snapControls\n"
            "{\n"
            "    nSmoothPatch    3;\n"
            "    tolerance       2.0;\n"
            "    nSolveIter      30;\n"
            "    nRelaxIter      5;\n"
            "    nFeatureSnapIter 10;\n"
            "    implicitFeatureSnap false;\n"
            "    explicitFeatureSnap true;\n"
            "    multiRegionFeatureSnap false;\n"
            "}\n"
            "addLayersControls\n"
            "{\n"
            "    relativeSizes   true;\n"
            "    layers          {}\n"
            "    expansionRatio  1.0;\n"
            "    finalLayerThickness 0.3;\n"
            "    minThickness    0.1;\n"
            "    nGrow           0;\n"
            "    featureAngle    60;\n"
            "    nRelaxIter      3;\n"
            "    nSmoothSurfaceNormals 1;\n"
            "    nSmoothNormals  3;\n"
            "    nSmoothThickness 10;\n"
            "    maxFaceThicknessRatio 0.5;\n"
            "    maxThicknessToMedialRatio 0.3;\n"
            "    minMedialAxisAngle 90;\n"
            "    nBufferCellsNoExtrude 0;\n"
            "    nLayerIter      50;\n"
            "}\n"
            "meshQualityControls\n"
            "{\n"
            "    maxNonOrtho     65;\n"
            "    maxBoundarySkewness 20;\n"
            "    maxInternalSkewness 4;\n"
            "    maxConcave      80;\n"
            "    minVol          1e-13;\n"
            "    minTetQuality   1e-15;\n"
            "    minArea         -1;\n"
            "    minTwist        0.02;\n"
            "    minDeterminant  0.001;\n"
            "    minFaceWeight   0.02;\n"
            "    minVolRatio     0.01;\n"
            "    minTriangleTwist -1;\n"
            "    nSmoothScale    4;\n"
            "    errorReduction  0.75;\n"
            "}\n"
            "mergeTolerance 1e-6;\n"
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
            "    p\n"
            "    {\n"
            "        solver          GAMG;\n"
            "        tolerance       1e-7;\n"
            "        relTol          0.01;\n"
            "        smoother        GaussSeidel;\n"
            "    }\n"
            "    U\n"
            "    {\n"
            "        solver          smoothSolver;\n"
            "        smoother        GaussSeidel;\n"
            "        tolerance       1e-8;\n"
            "        relTol          0.1;\n"
            "    }\n"
            "    \"(k|omega|epsilon)\"\n"
            "    {\n"
            "        solver          smoothSolver;\n"
            "        smoother        GaussSeidel;\n"
            "        tolerance       1e-8;\n"
            "        relTol          0.1;\n"
            "    }\n"
            "}\n"
            "SIMPLE\n"
            "{\n"
            "    nNonOrthogonalCorrectors 0;\n"
            "    consistent      yes;\n"
            "    residualControl\n"
            "    {\n"
            "        p               1e-3;\n"
            "        U               1e-4;\n"
            "    }\n"
            "}\n"
            "relaxationFactors\n"
            "{\n"
            "    equations\n"
            "    {\n"
            "        U           0.7;\n"
            "        \".*\"        0.7;\n"
            "    }\n"
            "    fields\n"
            "    {\n"
            "        p           0.3;\n"
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
