"""Unit tests for deterministic in-memory simulation sale generation."""

from datetime import datetime, timedelta, timezone

import pytest

from app.simulation import (
    DemandProfile,
    PumpState,
    RandomSource,
    SalesGenerator,
    StationSimulationState,
    TankState,
)
from app.utils.enums import PumpStatus

MOMENT = datetime(2026, 8, 3, 8, tzinfo=timezone.utc)


def _station(*, tank_level: float = 500.0, pump_count: int = 1) -> StationSimulationState:
    station = StationSimulationState(station_id=1)
    for index in range(1, pump_count + 1):
        tank = TankState(
            tank_id=index,
            station_id=1,
            fuel_type_id=1,
            code=f"T-{index}",
            capacity_liters=1_000.0,
            true_level_liters=tank_level,
            measured_level_liters=tank_level,
            minimum_safe_level=100.0,
            critical_level=50.0,
            temperature=20.0,
            water_level=0.0,
            sensor_status="OK",
        )
        station.add_tank(tank)
        station.add_pump(
            PumpState(
                pump_id=index,
                station_id=1,
                tank_id=index,
                fuel_type_id=1,
                code=f"P-{index}",
                status=PumpStatus.IDLE,
                nominal_flow_rate=42.0,
                minimum_flow_rate=10.0,
                maximum_motor_current=20.0,
                maximum_pressure=8.0,
            )
        )
    return station


def _generator(seed: int = 42) -> SalesGenerator:
    return SalesGenerator(random_source=RandomSource(seed), demand_profile=DemandProfile())


def _start(generator: SalesGenerator, station: StationSimulationState, **overrides: object):
    values = {
        "station_state": station,
        "pump_id": 1,
        "moment": MOMENT,
        "base_probability": 1.0,
        "fuel_code": "DIESEL",
        "unit_price": 45.0,
    }
    values.update(overrides)
    return generator.try_start_sale(**values)


def test_starts_sale_activates_pump_and_registers_state() -> None:
    station = _station()
    sale = _start(_generator(), station)

    assert sale is not None
    assert station.active_sales[1] is sale
    assert station.get_pump(1).status == PumpStatus.ACTIVE
    assert station.get_pump(1).flow_rate == 42.0


def test_non_start_leaves_state_unchanged() -> None:
    station = _station()

    assert _start(_generator(), station, base_probability=0.0) is None
    assert station.active_sales == {}
    assert station.get_pump(1).status == PumpStatus.IDLE
    assert station.get_tank(1).available_liters == 500.0


@pytest.mark.parametrize("probability", [-0.1, 1.1])
def test_rejects_invalid_probability(probability: float) -> None:
    with pytest.raises(ValueError, match="base_probability"):
        _start(_generator(), _station(), base_probability=probability)


@pytest.mark.parametrize("status", [PumpStatus.ACTIVE, PumpStatus.MAINTENANCE, PumpStatus.FAULT, PumpStatus.OFFLINE])
def test_non_idle_pump_cannot_start_sale(status: PumpStatus) -> None:
    station = _station()
    station.get_pump(1).status = status

    assert _start(_generator(), station) is None


def test_inactive_assets_and_low_stock_cannot_start_sale() -> None:
    station = _station(tank_level=0.5)
    assert _start(_generator(), station) is None
    station.get_tank(1).true_level_liters = 500.0
    station.get_tank(1).is_active = False
    assert _start(_generator(), station) is None
    station.get_tank(1).is_active = True
    station.get_pump(1).is_active = False
    assert _start(_generator(), station) is None


@pytest.mark.parametrize(
    ("fuel_code", "maximum"),
    [("MOTORIN", 120.0), ("BENZIN", 90.0), ("LPG", 70.0)],
)
def test_quantity_profiles_and_aliases(fuel_code: str, maximum: float) -> None:
    sale = _start(_generator(), _station(), fuel_code=fuel_code)

    assert sale is not None
    assert 5.0 <= sale.target_quantity_liters <= maximum


def test_rejects_unknown_fuel_and_naive_moment() -> None:
    with pytest.raises(ValueError, match="Unsupported fuel"):
        _start(_generator(), _station(), fuel_code="ELECTRIC")
    with pytest.raises(ValueError, match="timezone"):
        _start(_generator(), _station(), moment=MOMENT.replace(tzinfo=None))


def test_same_seed_and_calls_produce_same_target() -> None:
    first = _start(_generator(42), _station())
    second = _start(_generator(42), _station())

    assert first is not None and second is not None
    assert first.target_quantity_liters == second.target_quantity_liters


def test_target_is_capped_by_available_stock() -> None:
    station = _station(tank_level=3.0)
    sale = _start(_generator(), station)

    assert sale is not None
    assert sale.target_quantity_liters == 3.0
    assert station.get_tank(1).available_liters == 3.0


def test_advances_with_flow_formula_and_preserves_measured_level() -> None:
    station = _station()
    sale = _start(_generator(), station)
    assert sale is not None
    tank = station.get_tank(1)
    result = _generator().advance_active_sale(
        station_state=station,
        pump_id=1,
        elapsed_seconds=5,
        updated_at=MOMENT + timedelta(seconds=5),
    )

    assert result.dispensed_quantity_liters == pytest.approx(3.5)
    assert sale.dispensed_quantity_liters == pytest.approx(3.5)
    assert tank.available_liters == pytest.approx(496.5)
    assert tank.measured_level_liters == 500.0
    assert station.get_pump(1).total_working_hours == pytest.approx(5 / 3600)


@pytest.mark.parametrize("elapsed_seconds", [0, -1])
def test_rejects_invalid_advance_without_mutating_sale(elapsed_seconds: float) -> None:
    station = _station()
    sale = _start(_generator(), station)
    assert sale is not None

    with pytest.raises(ValueError, match="elapsed_seconds"):
        _generator().advance_active_sale(
            station_state=station,
            pump_id=1,
            elapsed_seconds=elapsed_seconds,
            updated_at=MOMENT + timedelta(seconds=1),
        )
    assert sale.dispensed_quantity_liters == 0.0
    assert station.get_tank(1).available_liters == 500.0


def test_rejects_naive_time_missing_sale_and_zero_flow() -> None:
    station = _station()
    with pytest.raises(KeyError, match="no active sale"):
        _generator().advance_active_sale(
            station_state=station, pump_id=1, elapsed_seconds=1, updated_at=MOMENT
        )
    sale = _start(_generator(), station)
    assert sale is not None
    station.get_pump(1).flow_rate = 0.0
    with pytest.raises(ValueError, match="timezone"):
        _generator().advance_active_sale(
            station_state=station,
            pump_id=1,
            elapsed_seconds=1,
            updated_at=MOMENT.replace(tzinfo=None),
        )
    with pytest.raises(ValueError, match="flow_rate"):
        _generator().advance_active_sale(
            station_state=station,
            pump_id=1,
            elapsed_seconds=1,
            updated_at=MOMENT + timedelta(seconds=1),
        )


def test_completion_clamps_final_tick_and_stops_pump() -> None:
    station = _station()
    sale = _start(_generator(), station)
    assert sale is not None
    sale.target_quantity_liters = 2.0
    result = _generator().advance_active_sale(
        station_state=station,
        pump_id=1,
        elapsed_seconds=5,
        updated_at=MOMENT + timedelta(seconds=5),
    )

    assert result.dispensed_quantity_liters == 2.0
    assert result.completed_sale is sale
    assert station.active_sales == {}
    assert station.get_pump(1).status == PumpStatus.IDLE
    assert station.get_pump(1).flow_rate == 0.0


def test_exhausted_tank_ends_sale_without_negative_level() -> None:
    station = _station(tank_level=3.0)
    sale = _start(_generator(), station)
    assert sale is not None
    result = _generator().advance_active_sale(
        station_state=station,
        pump_id=1,
        elapsed_seconds=10,
        updated_at=MOMENT + timedelta(seconds=10),
    )

    assert result.completed_sale is sale
    assert station.get_tank(1).available_liters == 0.0
    assert station.get_pump(1).status == PumpStatus.IDLE


def test_advances_multiple_sales_using_snapshot_order() -> None:
    station = _station(pump_count=2)
    generator = _generator()
    first = _start(generator, station, pump_id=1)
    second = _start(generator, station, pump_id=2)
    assert first is not None and second is not None
    first.target_quantity_liters = 2.0

    results = generator.advance_all_sales(
        station_state=station,
        elapsed_seconds=5,
        updated_at=MOMENT + timedelta(seconds=5),
    )

    assert [result.pump_id for result in results] == [1, 2]
    assert results[0].completed_sale is first
    assert results[1].dispensed_quantity_liters == pytest.approx(3.5)
    assert 2 in station.active_sales
