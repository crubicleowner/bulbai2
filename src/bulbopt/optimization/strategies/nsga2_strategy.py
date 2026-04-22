"""pymoo NSGA-II adapter for the 8-D Kracht bulb parametric space.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §6.

NSGA-II is a multi-objective evolutionary algorithm that maintains a
population of candidate solutions, selects non-dominated individuals via
the fast-non-dominated-sort + crowding-distance heuristic, and evolves
toward the Pareto front. It is the textbook fit for our problem shape:
8 continuous vars, 2 objectives (drag + volume delta), small population,
modest generation count, black-box evaluator.

This module wraps ``pymoo.algorithms.moo.nsga2.NSGA2`` with a thin
adapter that:

* Translates our :class:`KrachtDesignSpace` bounds into pymoo's ``xl``
  and ``xu`` arrays (preserving KRACHT_PARAMETER_NAMES order).
* Lets the caller plug a simple ``evaluate(list[KrachtVector]) -> list[list[float]]``
  black box instead of subclassing ``pymoo.Problem``.
* Emits a per-generation callback carrying ``{generation, evaluations,
  non_dominated_count}`` so the UI/CLI can render progress.
* Returns a pure-Python :class:`ParetoFront` free of pymoo dependencies
  so downstream code (reporting, checkpoints) doesn't leak the algorithm
  library.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Mapping, Sequence

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.callback import Callback
from pymoo.core.problem import Problem
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.optimize import minimize

from bulbopt.optimization.parametric.kracht_space import (
    KRACHT_PARAMETER_NAMES,
    KrachtDesignSpace,
    KrachtVector,
)


EvaluateFn = Callable[[List[KrachtVector]], List[List[float]]]


@dataclass(slots=True, frozen=True)
class ParetoCandidate:
    """One non-dominated individual from the final population."""

    vector: KrachtVector
    objectives: List[float]


@dataclass(slots=True, frozen=True)
class ParetoFront:
    """Final output of :meth:`NSGA2Strategy.optimize`."""

    candidates: List[ParetoCandidate]


class NSGA2Strategy:
    """NSGA-II driver for the Kracht space.

    Parameters
    ----------
    population:
        Number of individuals per generation. Also the upper bound on the
        Pareto front size because pymoo keeps the population non-dominated.
    generations:
        Number of generations (the "n_gen" termination criterion).
    seed:
        Seed fed to pymoo's RNG — makes runs reproducible.
    on_generation:
        Optional callback that fires once per generation with a dict
        ``{"generation": int, "evaluations": int, "non_dominated_count": int}``.
    """

    def __init__(
        self,
        population: int = 50,
        generations: int = 20,
        seed: int | None = None,
        on_generation: Callable[[Mapping[str, int]], None] | None = None,
        n_objectives: int = 2,
    ) -> None:
        if population < 2:
            raise ValueError("population must be >= 2")
        if generations < 1:
            raise ValueError("generations must be >= 1")
        if n_objectives < 1:
            raise ValueError("n_objectives must be >= 1")
        self.population = int(population)
        self.generations = int(generations)
        self.seed = seed
        self.on_generation = on_generation
        self.n_objectives = int(n_objectives)

    def optimize(
        self,
        *,
        space: KrachtDesignSpace,
        evaluate: EvaluateFn,
    ) -> ParetoFront:
        problem = _KrachtProblem(
            space=space,
            evaluate=evaluate,
            n_objectives=self.n_objectives,
        )
        algo = NSGA2(
            pop_size=self.population,
            sampling=FloatRandomSampling(),
        )
        callback = _GenerationCallback(
            strategy=self,
            problem=problem,
        )
        result = minimize(
            problem,
            algo,
            termination=("n_gen", self.generations),
            seed=self.seed,
            verbose=False,
            callback=callback,
            save_history=False,
        )
        if result.X is None or result.F is None:
            return ParetoFront(candidates=[])

        candidates: List[ParetoCandidate] = []
        X = np.atleast_2d(result.X)
        F = np.atleast_2d(result.F)
        for row, objectives in zip(X, F):
            vector = space.from_array([float(v) for v in row])
            candidates.append(
                ParetoCandidate(
                    vector=vector,
                    objectives=[float(value) for value in objectives],
                )
            )
        return ParetoFront(candidates=candidates)


class _KrachtProblem(Problem):
    """Adapter: pymoo Problem backed by our ``evaluate`` callable."""

    def __init__(
        self,
        *,
        space: KrachtDesignSpace,
        evaluate: EvaluateFn,
        n_objectives: int,
    ) -> None:
        xl = np.array([space.bounds[name][0] for name in KRACHT_PARAMETER_NAMES])
        xu = np.array([space.bounds[name][1] for name in KRACHT_PARAMETER_NAMES])
        super().__init__(n_var=len(xl), n_obj=n_objectives, xl=xl, xu=xu)
        self._space = space
        self._evaluate_fn = evaluate

    def _evaluate(self, X, out, *args, **kwargs):  # pymoo Problem API
        vectors = [
            self._space.from_array([float(v) for v in row])
            for row in np.atleast_2d(X)
        ]
        objectives = self._evaluate_fn(vectors)
        out["F"] = np.asarray(objectives, dtype=float)


class _GenerationCallback(Callback):
    """Per-generation pymoo callback that fans out to user on_generation."""

    def __init__(self, *, strategy: NSGA2Strategy, problem: Problem) -> None:
        super().__init__()
        self._strategy = strategy
        self._problem = problem
        self._generation_index = 0
        self._evaluations_so_far = 0

    def notify(self, algorithm) -> None:  # pymoo API
        pop = algorithm.pop
        if pop is None:
            return
        self._evaluations_so_far += len(pop)
        cb = self._strategy.on_generation
        if cb is None:
            self._generation_index += 1
            return
        opt = algorithm.opt
        non_dominated_count = 0 if opt is None else len(opt)
        cb(
            {
                "generation": self._generation_index,
                "evaluations": self._evaluations_so_far,
                "non_dominated_count": non_dominated_count,
            }
        )
        self._generation_index += 1
