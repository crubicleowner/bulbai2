"""Tests for the runtime-budget scheduler.

Design reference: 2026-04-22-bulbopt-night-optimization-design.md §7.
The scheduler tracks wall-clock consumption per gate and lets the cascade
strategy short-circuit when the runtime budget approaches exhaustion.
"""
from __future__ import annotations

import pytest

from bulbopt.optimization.scheduler.budget_scheduler import (
    BudgetExhausted,
    BudgetScheduler,
)


def test_scheduler_tracks_remaining_budget_after_allocations() -> None:
    scheduler = BudgetScheduler(runtime_budget_hours=1.0, clock=lambda: 0.0)

    scheduler.allocate(gate="fast_screen", seconds=600)   # 10 min
    assert scheduler.remaining_seconds == pytest.approx(3000.0)  # 3600 - 600
    scheduler.allocate(gate="mid", seconds=1200)           # 20 min
    assert scheduler.remaining_seconds == pytest.approx(1800.0)


def test_scheduler_reports_gate_timings() -> None:
    scheduler = BudgetScheduler(runtime_budget_hours=2.0, clock=lambda: 0.0)
    scheduler.allocate(gate="fast_screen", seconds=100)
    scheduler.allocate(gate="mid", seconds=500)
    scheduler.allocate(gate="fast_screen", seconds=200)  # second pass

    timings = scheduler.gate_timings()
    assert timings["fast_screen"] == pytest.approx(300.0)
    assert timings["mid"] == pytest.approx(500.0)


def test_scheduler_is_budget_critical_past_threshold() -> None:
    """Cascade uses is_critical() to decide when to stop scheduling new
    generations and jump to the final high-fidelity pass."""
    scheduler = BudgetScheduler(
        runtime_budget_hours=1.0,
        critical_threshold=0.8,
        clock=lambda: 0.0,
    )
    scheduler.allocate(gate="mid", seconds=2500)  # ~69% used
    assert scheduler.is_critical() is False
    scheduler.allocate(gate="mid", seconds=500)   # ~83% used
    assert scheduler.is_critical() is True


def test_scheduler_raises_when_hard_budget_exceeded() -> None:
    """At hard limit, allocate raises so the caller can abort gracefully."""
    scheduler = BudgetScheduler(runtime_budget_hours=0.5, clock=lambda: 0.0)
    scheduler.allocate(gate="mid", seconds=1800)  # exactly 100%
    with pytest.raises(BudgetExhausted):
        scheduler.allocate(gate="mid", seconds=1)


def test_scheduler_trace_entries_order_preserved() -> None:
    scheduler = BudgetScheduler(runtime_budget_hours=1.0, clock=lambda: 0.0)
    scheduler.allocate(gate="fast", seconds=10)
    scheduler.allocate(gate="mid", seconds=20)
    scheduler.allocate(gate="high", seconds=30)

    trace = scheduler.trace()
    assert [entry["gate"] for entry in trace] == ["fast", "mid", "high"]
    assert [entry["seconds"] for entry in trace] == [10, 20, 30]
    # Every entry has a cumulative elapsed field for debugging.
    assert trace[0]["cumulative_seconds"] == 10
    assert trace[1]["cumulative_seconds"] == 30
    assert trace[2]["cumulative_seconds"] == 60


def test_scheduler_clock_mode_seeds_reference_then_charges_delta() -> None:
    """Clock mode: first ``seconds=None`` seeds the reference tick with a
    zero charge; subsequent ``seconds=None`` calls charge the delta since
    the previous clock tick."""
    ticks = iter([0.0, 10.0, 30.0])

    def fake_clock() -> float:
        return next(ticks)

    scheduler = BudgetScheduler(runtime_budget_hours=1.0, clock=fake_clock)
    scheduler.allocate(gate="fast", seconds=None)  # tick 0.0, charges 0
    scheduler.allocate(gate="mid", seconds=None)   # tick 10.0, charges 10
    scheduler.allocate(gate="high", seconds=None)  # tick 30.0, charges 20

    trace = scheduler.trace()
    assert len(trace) == 3
    assert trace[0]["seconds"] == pytest.approx(0.0)
    assert trace[1]["seconds"] == pytest.approx(10.0)
    assert trace[2]["seconds"] == pytest.approx(20.0)
