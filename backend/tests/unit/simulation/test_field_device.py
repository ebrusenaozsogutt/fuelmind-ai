"""Focused coverage for field-device views of existing simulation values."""

from datetime import datetime, timezone

from app.simulation.demand_profile import DemandProfile
from app.simulation.field_device import DEFAULT_TANK_HEIGHT_MM, derive_probe_observations
from app.simulation.random_source import RandomSource
from app.simulation.sales_generator import SalesGenerator
from app.simulation.state import (
    NozzleState,
    PumpState,
    StationSimulationState,
    TankProbeState,
    TankState,
)
from app.utils.enums import NozzleStatus, ProbeStatus, PumpStatus

MOMENT = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)


def _station() -> StationSimulationState:
    station = StationSimulationState(station_id=1)
    station.add_tank(
        TankState(
            tank_id=1,
            station_id=1,
            fuel_type_id=1,
            code="T-1",
            capacity_liters=1_000,
            true_level_liters=720,
            measured_level_liters=650,
            minimum_safe_level=100,
            critical_level=50,
            temperature=18.7,
            water_level=5,
            sensor_status="OK",
        )
    )
    station.add_pump(
        PumpState(
            pump_id=1,
            station_id=1,
            tank_id=1,
            fuel_type_id=1,
            code="P-1",
            status=PumpStatus.IDLE,
            nominal_flow_rate=42,
            minimum_flow_rate=10,
            maximum_motor_current=20,
            maximum_pressure=8,
        )
    )
    return station


def _start_sale(station: StationSimulationState, seed: int = 42):
    return SalesGenerator(
        random_source=RandomSource(seed), demand_profile=DemandProfile()
    ).try_start_sale(
        station_state=station,
        pump_id=1,
        moment=MOMENT,
        base_probability=1,
        fuel_code="DIESEL",
        unit_price=45,
    )


def test_online_probe_reuses_measured_values_and_bounded_demo_heights() -> None:
    station = _station()
    station.add_active_probe(TankProbeState(11, 1, ProbeStatus.ONLINE, True))

    [observation] = derive_probe_observations(station)

    assert observation.probe_id == 11
    assert observation.fuel_volume_liters == 650
    assert observation.temperature_celsius == 18.7
    assert observation.water_volume_liters == 5
    assert observation.fuel_height_mm == 1_300
    assert observation.water_height_mm == 10
    assert 0 <= observation.fuel_height_mm <= DEFAULT_TANK_HEIGHT_MM


def test_probe_observation_follows_measured_sensor_stuck_value_and_water_change() -> None:
    station = _station()
    station.add_active_probe(TankProbeState(11, 1, ProbeStatus.ONLINE, True))
    first = derive_probe_observations(station)[0]
    tank = station.get_tank(1)

    # A sensor-stuck scenario changes physical level while retaining its measurement.
    tank.true_level_liters = 600
    tank.water_level = 8
    second = derive_probe_observations(station)[0]

    assert second.fuel_volume_liters == first.fuel_volume_liters
    assert second.fuel_height_mm == first.fuel_height_mm
    assert second.water_volume_liters == 8
    assert second.water_height_mm > first.water_height_mm


def test_offline_and_fault_probes_do_not_produce_observations() -> None:
    for status in (ProbeStatus.OFFLINE, ProbeStatus.FAULT):
        station = _station()
        station.add_active_probe(TankProbeState(11, 1, status, True))
        assert derive_probe_observations(station) == []


def test_nozzle_selection_is_seeded_and_excludes_unavailable_nozzles() -> None:
    first_station = _station()
    second_station = _station()
    for station in (first_station, second_station):
        station.add_nozzle(NozzleState(10, 1, 1, NozzleStatus.AVAILABLE, True))
        station.add_nozzle(NozzleState(11, 1, 1, NozzleStatus.AVAILABLE, True))
        station.add_nozzle(NozzleState(12, 1, 1, NozzleStatus.FAULT, True))
        station.add_nozzle(NozzleState(13, 1, 1, NozzleStatus.OUT_OF_SERVICE, True))

    first = _start_sale(first_station, seed=7)
    second = _start_sale(second_station, seed=7)

    assert first is not None and second is not None
    assert first.nozzle_id in {10, 11}
    assert first.nozzle_id == second.nozzle_id


def test_legacy_pump_sale_remains_valid_without_nozzle() -> None:
    sale = _start_sale(_station())

    assert sale is not None
    assert sale.nozzle_id is None
