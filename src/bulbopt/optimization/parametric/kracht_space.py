"""Kracht-style bulb parametric space.

Design reference: docs/superpowers/specs/2026-04-22-bulbopt-night-optimization-design.md §4.1.

Eight continuous design variables with physical meaning, bounded by values
adapted from Kracht (1978) and Hoekstra/Raven (2011). The space provides
three services for the optimization layer:

1. ``sample(n, seed)`` — Latin-hypercube-style uniform sampling inside the
   bounds. Deterministic under a fixed seed so NSGA-II runs are reproducible.
2. ``validate(vector)`` — binary check that every parameter is present and
   inside its declared range.
3. ``to_array`` / ``from_array`` — canonical conversion between the dict
   form (human-readable, JSON-friendly) and the numpy-friendly float vector
   used by pymoo operators.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Tuple


# Declared in the order the GA array uses. Do not reorder without updating
# existing case payloads — this order is part of the public schema.
KRACHT_PARAMETER_NAMES: Tuple[str, ...] = (
    "length_ratio",
    "breadth_ratio",
    "height_ratio",
    "axis_z_ratio",
    "longitudinal_pos",
    "cross_section_c",
    "volume_coef",
    "nose_sharpness",
)


_DEFAULT_BOUNDS: Dict[str, Tuple[float, float]] = {
    "length_ratio":     (0.010, 0.045),
    "breadth_ratio":    (0.015, 0.200),
    "height_ratio":     (0.100, 0.650),
    "axis_z_ratio":     (0.050, 0.500),
    "longitudinal_pos": (0.000, 1.000),
    "cross_section_c":  (0.250, 1.000),
    "volume_coef":      (0.400, 0.900),
    "nose_sharpness":   (0.000, 1.000),
}


@dataclass(slots=True, frozen=True)
class KrachtVector:
    """One concrete 8-parameter sample.

    ``values`` must contain every KRACHT_PARAMETER_NAMES key. The dataclass
    is frozen so a vector can safely be cached / checkpointed.
    """

    values: Mapping[str, float]


@dataclass(slots=True)
class KrachtDesignSpace:
    """Bounded 8-D design space.

    Bounds default to the values from the design spec §4.1; callers may
    override them (e.g. tighter ranges for a local_optimize refinement).
    """

    bounds: Dict[str, Tuple[float, float]] = field(default_factory=lambda: dict(_DEFAULT_BOUNDS))

    def sample(self, n: int, seed: int | None = None) -> List[KrachtVector]:
        """Uniform random sample of ``n`` vectors.

        We use :mod:`random` rather than :mod:`numpy.random` so the outputs
        serialise directly to plain floats without numpy wrapping the values
        (important for JSON checkpointing).
        """
        rng = random.Random(seed)
        samples: List[KrachtVector] = []
        for _ in range(int(n)):
            values = {
                name: rng.uniform(*self.bounds[name])
                for name in KRACHT_PARAMETER_NAMES
            }
            samples.append(KrachtVector(values=values))
        return samples

    def validate(self, vector: KrachtVector) -> bool:
        """Return True iff ``vector`` has every declared parameter in range."""
        values = vector.values
        for name in KRACHT_PARAMETER_NAMES:
            if name not in values:
                return False
            lo, hi = self.bounds[name]
            value = float(values[name])
            if value < lo or value > hi:
                return False
        return True

    def to_array(self, vector: KrachtVector) -> List[float]:
        """Convert a vector to a list of floats in declared order."""
        return [float(vector.values[name]) for name in KRACHT_PARAMETER_NAMES]

    def from_array(self, array: Iterable[float]) -> KrachtVector:
        """Invert :meth:`to_array` — build a KrachtVector from a float list."""
        values = {
            name: float(value)
            for name, value in zip(KRACHT_PARAMETER_NAMES, array, strict=True)
        }
        return KrachtVector(values=values)
