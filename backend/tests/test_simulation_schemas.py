"""Validation coverage for simulation REST request schemas."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.simulation_run import SimulationRunCreate
from app.utils.enums import SimulationMode
from app.utils.simulation_defaults import DEFAULT_TICK_INTERVAL_MS


def test_simulation_create_uses_canonical_defaults() -> None:
    payload = SimulationRunCreate(station_id=1)

    assert payload.mode == SimulationMode.REALTIME
    assert payload.tick_interval_ms == DEFAULT_TICK_INTERVAL_MS


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tick_interval_ms", 0),
        ("simulation_step_seconds", 0),
        ("speed_multiplier", 0),
        ("persist_every_n_ticks", 0),
    ],
)
def test_simulation_create_rejects_invalid_runtime_values(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        SimulationRunCreate(station_id=1, **{field: value})


@pytest.mark.parametrize("mode", list(SimulationMode))
def test_simulation_create_accepts_each_mode(mode: SimulationMode) -> None:
    assert SimulationRunCreate(station_id=1, mode=mode).mode == mode


def test_simulation_create_requires_timezone_aware_start_time() -> None:
    with pytest.raises(ValidationError):
        SimulationRunCreate(station_id=1, simulation_start_time=datetime(2026, 1, 1))

    assert SimulationRunCreate(
        station_id=1,
        simulation_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
