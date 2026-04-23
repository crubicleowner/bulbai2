"""Parser for OpenFOAM ``forces`` / ``forceCoeffs`` coefficient.dat files.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §9.

The forceCoeffs function object writes one row per reported timestep:

    # Forces coefficient output
    # Column 1: Time
    # Column 2: Cd
    # Column 3: Cs
    # Column 4: Cl
    0.0  1.2345  0.0  0.0
    1.0  0.9100  0.0  0.0
    ...

The parser:

* skips comment (``#``) and blank lines,
* extracts the last numeric row's Cd (column 2) as the converged drag
  coefficient (assumes the solver wrote the final converged state),
* optionally converts Cd to a drag force in Newtons when the caller
  supplies a reference velocity, area, and fluid density:
      F_drag = Cd * 0.5 * rho * V^2 * A
  so the cascade can feed Newtons straight into the GA objective.

The parser returns a plain dict so the result serialises to JSON without
transformation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


class ForceCoeffsNotFoundError(FileNotFoundError):
    """Raised when the expected coefficient.dat does not exist."""


def parse_drag_coefficient_dat(
    path: Path,
    *,
    reference_velocity_m_s: Optional[float] = None,
    reference_area_m2: Optional[float] = None,
    fluid_density_kg_m3: Optional[float] = None,
) -> dict:
    """Return final drag info from an OpenFOAM forceCoeffs output file."""
    path = Path(path)
    if not path.exists():
        raise ForceCoeffsNotFoundError(str(path))

    rows: list[tuple[float, float]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 2:
                continue
            try:
                time_s = float(parts[0])
                cd = float(parts[1])
            except ValueError:
                continue
            rows.append((time_s, cd))

    if not rows:
        raise ValueError(
            f"forceCoeffs file has no data rows: {path}"
        )

    final_time, final_cd = rows[-1]
    result: dict = {
        "final_cd": final_cd,
        "iterations": len(rows),
        "final_time": final_time,
    }

    if (
        reference_velocity_m_s is not None
        and reference_area_m2 is not None
        and fluid_density_kg_m3 is not None
    ):
        drag_newtons = (
            final_cd
            * 0.5
            * float(fluid_density_kg_m3)
            * float(reference_velocity_m_s) ** 2
            * float(reference_area_m2)
        )
        result["drag_newtons"] = drag_newtons
    else:
        result["drag_newtons"] = None

    return result
