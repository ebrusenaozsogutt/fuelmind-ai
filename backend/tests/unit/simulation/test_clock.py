"""Simulation clock tests."""

from datetime import datetime, timedelta, timezone

import pytest

from app.simulation.clock import SimulationClock
from app.simulation.config import SimulationConfig


def test_aware_start_time_is_preserved_as_utc() -> None:
    start_time = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)

    assert SimulationClock(start_time=start_time).current_time == start_time


def test_naive_start_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        SimulationClock(start_time=datetime(2026, 8, 6, 12, 0))


def test_clock_advances_by_configured_step() -> None:
    clock = SimulationClock(
        SimulationConfig(simulation_step_seconds=5),
        datetime(2026, 8, 6, tzinfo=timezone.utc),
    )

    assert clock.advance() == datetime(2026, 8, 6, 0, 0, 5, tzinfo=timezone.utc)


def test_speed_multiplier_changes_advance_amount() -> None:
    start_time = datetime(2026, 8, 6, tzinfo=timezone.utc)
    clock = SimulationClock(SimulationConfig(simulation_step_seconds=5), start_time)
    clock.set_speed(2.5)

    assert clock.advance() == start_time + timedelta(seconds=12.5)


def test_pause_and_resume_control_advancement() -> None:
    start_time = datetime(2026, 8, 6, tzinfo=timezone.utc)
    clock = SimulationClock(start_time=start_time)
    clock.pause()

    assert clock.advance() == start_time
    clock.resume()
    assert clock.advance() == start_time + timedelta(seconds=5)


@pytest.mark.parametrize("speed", [0, -1])
def test_invalid_speed_is_rejected(speed: float) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        SimulationClock().set_speed(speed)


def test_multiple_advances_are_cumulative() -> None:
    start_time = datetime(2026, 8, 6, tzinfo=timezone.utc)
    clock = SimulationClock(start_time=start_time)

    clock.advance()
    clock.advance()

    assert clock.current_time == start_time + timedelta(seconds=10)
