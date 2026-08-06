"""In-memory simulation state tests."""

from datetime import datetime, timedelta, timezone

import pytest

from app.simulation.state import (
    ActiveSaleState,
    PumpState,
    StationSimulationState,
    TankState,
)
from app.utils.enums import PumpStatus

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def make_tank(**overrides: object) -> TankState:
    values: dict[str, object] = {
        "tank_id": 1,
        "station_id": 1,
        "fuel_type_id": 1,
        "code": "T-1",
        "capacity_liters": 100.0,
        "true_level_liters": 50.0,
        "measured_level_liters": 48.0,
        "minimum_safe_level": 20.0,
        "critical_level": 10.0,
        "temperature": 15.0,
        "water_level": 0.0,
        "sensor_status": "ACTIVE",
    }
    values.update(overrides)
    return TankState(**values)  # type: ignore[arg-type]


def make_pump(**overrides: object) -> PumpState:
    values: dict[str, object] = {
        "pump_id": 1,
        "station_id": 1,
        "tank_id": 1,
        "fuel_type_id": 1,
        "code": "P-1",
        "status": PumpStatus.IDLE,
        "nominal_flow_rate": 10.0,
        "minimum_flow_rate": 1.0,
        "maximum_motor_current": 5.0,
        "maximum_pressure": 3.0,
    }
    values.update(overrides)
    return PumpState(**values)  # type: ignore[arg-type]


def make_sale(**overrides: object) -> ActiveSaleState:
    values: dict[str, object] = {
        "sale_id": "sale-1",
        "station_id": 1,
        "tank_id": 1,
        "pump_id": 1,
        "fuel_type_id": 1,
        "started_at": NOW,
        "target_quantity_liters": 10.0,
        "dispensed_quantity_liters": 0.0,
        "unit_price": 45.5,
    }
    values.update(overrides)
    return ActiveSaleState(**values)  # type: ignore[arg-type]


def test_tank_state_validates_levels_and_updates_independently() -> None:
    tank = make_tank()
    assert tank.available_liters == 50.0
    assert tank.fill_percentage == 50.0
    tank.withdraw(10)
    assert tank.true_level_liters == 40.0
    assert tank.measured_level_liters == 48.0
    tank.receive(20)
    tank.update_measured_level(61)
    assert tank.true_level_liters == 60.0
    assert tank.measured_level_liters == 61.0


@pytest.mark.parametrize(
    "overrides",
    [
        {"true_level_liters": -1},
        {"measured_level_liters": 101},
        {"minimum_safe_level": 101},
        {"water_level": -1},
    ],
)
def test_tank_state_rejects_invalid_initial_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        make_tank(**overrides)


def test_tank_rejects_invalid_withdrawals_and_receipts() -> None:
    tank = make_tank()
    with pytest.raises(ValueError):
        tank.withdraw(51)
    with pytest.raises(ValueError):
        tank.withdraw(0)
    with pytest.raises(ValueError):
        tank.receive(51)
    with pytest.raises(ValueError):
        tank.update_measured_level(101)


def test_pump_state_controls_dispensing_and_sensor_values() -> None:
    pump = make_pump()
    assert pump.is_idle
    pump.start_dispensing()
    assert pump.is_active_status
    pump.set_sensor_values(
        flow_rate=4, pressure=2, motor_current=3, temperature=25
    )
    pump.increment_working_time(1800)
    pump.increment_error_count()
    pump.stop_dispensing()
    assert pump.status == PumpStatus.IDLE
    assert (pump.flow_rate, pump.pressure, pump.motor_current) == (0.0, 0.0, 0.0)
    assert pump.total_working_hours == 0.5
    assert pump.error_count == 1


@pytest.mark.parametrize("status", [PumpStatus.MAINTENANCE, PumpStatus.FAULT, PumpStatus.OFFLINE])
def test_unavailable_pump_cannot_start_dispensing(status: PumpStatus) -> None:
    with pytest.raises(ValueError):
        make_pump(status=status).start_dispensing()


def test_pump_rejects_negative_sensor_values_and_duration() -> None:
    pump = make_pump()
    with pytest.raises(ValueError):
        pump.set_sensor_values(flow_rate=-1, pressure=0, motor_current=0, temperature=0)
    with pytest.raises(ValueError):
        pump.increment_working_time(-1)


def test_active_sale_tracks_progress_and_clamps_final_dispense() -> None:
    sale = make_sale()
    assert sale.remaining_quantity_liters == 10.0
    assert sale.dispense(4, NOW + timedelta(seconds=1)) == 4.0
    assert sale.progress_percentage == 40.0
    assert sale.dispense(10, NOW + timedelta(seconds=2)) == 6.0
    assert sale.is_completed
    with pytest.raises(ValueError):
        sale.dispense(1, NOW + timedelta(seconds=3))


def test_active_sale_rejects_invalid_times_and_quantities() -> None:
    with pytest.raises(ValueError):
        make_sale(started_at=datetime(2026, 8, 6, 12, 0))
    sale = make_sale()
    with pytest.raises(ValueError):
        sale.dispense(1, NOW - timedelta(seconds=1))
    with pytest.raises(ValueError):
        sale.dispense(0, NOW + timedelta(seconds=1))


def test_station_state_enforces_relationships_and_sale_lifecycle() -> None:
    state = StationSimulationState(1)
    tank = make_tank()
    pump = make_pump()
    sale = make_sale()
    state.add_tank(tank)
    state.add_pump(pump)
    state.start_sale(sale)
    assert state.has_active_sale(pump.pump_id)
    assert state.get_active_sale(pump.pump_id) is sale
    assert state.complete_sale(pump.pump_id) is sale
    assert not state.has_active_sale(pump.pump_id)
    assert (state.next_sequence(), state.next_sequence()) == (1, 2)


def test_station_state_rejects_duplicate_and_incompatible_members() -> None:
    state = StationSimulationState(1)
    tank = make_tank()
    state.add_tank(tank)
    with pytest.raises(ValueError):
        state.add_tank(tank)
    with pytest.raises(ValueError):
        state.add_tank(make_tank(tank_id=2, station_id=2))
    with pytest.raises(ValueError):
        state.add_pump(make_pump(fuel_type_id=2))
    with pytest.raises(KeyError):
        state.add_pump(make_pump(tank_id=99))


def test_station_state_rejects_second_or_incompatible_sale() -> None:
    state = StationSimulationState(1)
    state.add_tank(make_tank())
    state.add_pump(make_pump())
    state.start_sale(make_sale())
    with pytest.raises(ValueError):
        state.start_sale(make_sale(sale_id="sale-2"))
    state.complete_sale(1)
    with pytest.raises(ValueError):
        state.start_sale(make_sale(fuel_type_id=2))


def test_station_states_do_not_share_mutable_collections() -> None:
    first = StationSimulationState(1)
    second = StationSimulationState(2)
    first.add_tank(make_tank())

    assert second.tanks == {}
