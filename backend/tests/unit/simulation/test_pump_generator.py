"""Unit tests for deterministic pump sensor generation."""

import pytest

from app.simulation import PumpGenerator, PumpState, RandomSource
from app.utils.enums import PumpStatus


def _pump(*, status: PumpStatus = PumpStatus.ACTIVE, is_active: bool = True) -> PumpState:
    return PumpState(
        pump_id=1,
        station_id=1,
        tank_id=1,
        fuel_type_id=1,
        code="P-1",
        status=status,
        nominal_flow_rate=42.0,
        minimum_flow_rate=10.0,
        maximum_motor_current=20.0,
        maximum_pressure=8.0,
        flow_rate=1.0 if status == PumpStatus.ACTIVE else 0.0,
        pressure=1.0 if status == PumpStatus.ACTIVE else 0.0,
        motor_current=1.0 if status == PumpStatus.ACTIVE else 0.0,
        temperature=20.0,
        is_active=is_active,
    )


def test_active_pump_sensors_stay_within_physical_limits() -> None:
    pump = _pump()
    result = PumpGenerator(random_source=RandomSource(42)).update_pump(
        pump=pump, elapsed_seconds=5
    )

    assert result is pump
    assert pump.minimum_flow_rate <= pump.flow_rate <= pump.nominal_flow_rate * 1.15
    assert 0.0 <= pump.pressure <= pump.maximum_pressure
    assert 0.0 <= pump.motor_current <= pump.maximum_motor_current
    assert pump.temperature >= 0.0
    assert pump.total_working_hours == 0.0


def test_same_seed_produces_same_sensor_values() -> None:
    first = _pump()
    second = _pump()
    first_generator = PumpGenerator(random_source=RandomSource(7))
    second_generator = PumpGenerator(random_source=RandomSource(7))

    first_generator.update_pump(pump=first, elapsed_seconds=5)
    second_generator.update_pump(pump=second, elapsed_seconds=5)

    assert (first.flow_rate, first.pressure, first.motor_current, first.temperature) == (
        second.flow_rate,
        second.pressure,
        second.motor_current,
        second.temperature,
    )


@pytest.mark.parametrize("status", [PumpStatus.IDLE, PumpStatus.MAINTENANCE, PumpStatus.FAULT, PumpStatus.OFFLINE])
def test_non_dispensing_pump_resets_flow_sensors(status: PumpStatus) -> None:
    pump = _pump(status=status)
    pump.flow_rate, pump.pressure, pump.motor_current = 10.0, 2.0, 3.0

    PumpGenerator(random_source=RandomSource(42)).update_pump(pump=pump, elapsed_seconds=5)

    assert (pump.flow_rate, pump.pressure, pump.motor_current) == (0.0, 0.0, 0.0)
    assert pump.status == status


def test_inactive_active_status_pump_resets_flow_sensors() -> None:
    pump = _pump(is_active=False)
    PumpGenerator(random_source=RandomSource(42)).update_pump(pump=pump, elapsed_seconds=5)

    assert (pump.flow_rate, pump.pressure, pump.motor_current) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("elapsed_seconds", [0, -1, float("nan")])
def test_rejects_invalid_elapsed_seconds(elapsed_seconds: float) -> None:
    with pytest.raises(ValueError, match="elapsed_seconds"):
        PumpGenerator(random_source=RandomSource(42)).update_pump(
            pump=_pump(), elapsed_seconds=elapsed_seconds
        )


def test_updates_pumps_in_input_order() -> None:
    pumps = [_pump(), _pump()]
    pumps[1].pump_id = 2
    result = PumpGenerator(random_source=RandomSource(42)).update_pumps(
        pumps=pumps, elapsed_seconds=5
    )

    assert result == pumps
