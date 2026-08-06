"""Unit tests for deterministic tank sensor generation."""

import pytest

from app.simulation import RandomSource, TankGenerator, TankState


def _tank(*, is_active: bool = True) -> TankState:
    return TankState(
        tank_id=1,
        station_id=1,
        fuel_type_id=1,
        code="T-1",
        capacity_liters=1_000.0,
        true_level_liters=500.0,
        measured_level_liters=500.0,
        minimum_safe_level=100.0,
        critical_level=50.0,
        temperature=20.0,
        water_level=0.1,
        sensor_status="ACTIVE",
        is_active=is_active,
    )


def test_updates_measurement_without_changing_physical_stock() -> None:
    tank = _tank()
    result = TankGenerator(random_source=RandomSource(42)).update_tank(
        tank=tank, elapsed_seconds=5
    )

    assert result is tank
    assert tank.true_level_liters == 500.0
    assert 0.0 <= tank.measured_level_liters <= tank.capacity_liters
    assert tank.temperature != 20.0
    assert tank.water_level >= 0.0


def test_same_seed_produces_same_measurement() -> None:
    first = _tank()
    second = _tank()

    TankGenerator(random_source=RandomSource(7)).update_tank(
        tank=first, elapsed_seconds=10
    )
    TankGenerator(random_source=RandomSource(7)).update_tank(
        tank=second, elapsed_seconds=10
    )

    assert first.measured_level_liters == second.measured_level_liters
    assert first.temperature == second.temperature
    assert first.water_level == second.water_level


def test_inactive_tank_is_not_changed() -> None:
    tank = _tank(is_active=False)
    TankGenerator(random_source=RandomSource(42)).update_tank(tank=tank, elapsed_seconds=5)

    assert (tank.measured_level_liters, tank.temperature, tank.water_level) == (
        500.0,
        20.0,
        0.1,
    )


@pytest.mark.parametrize("elapsed_seconds", [0, -1, float("inf")])
def test_rejects_invalid_elapsed_seconds(elapsed_seconds: float) -> None:
    with pytest.raises(ValueError, match="elapsed_seconds"):
        TankGenerator(random_source=RandomSource(42)).update_tank(
            tank=_tank(), elapsed_seconds=elapsed_seconds
        )


def test_updates_tanks_in_input_order() -> None:
    tanks = [_tank(), _tank()]
    tanks[1].tank_id = 2
    result = TankGenerator(random_source=RandomSource(42)).update_tanks(
        tanks=tanks, elapsed_seconds=5
    )

    assert result == tanks
