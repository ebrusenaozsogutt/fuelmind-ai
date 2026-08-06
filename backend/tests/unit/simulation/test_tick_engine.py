from datetime import datetime, timezone

import pytest

from app.simulation import (
    DeliveryGenerator,
    DemandProfile,
    PumpGenerator,
    PumpState,
    RandomSource,
    SalesGenerator,
    SimulationClock,
    SimulationConfig,
    SimulationValidator,
    StationSimulationState,
    TankGenerator,
    TankState,
    TickEngine,
)
from app.utils.enums import PumpStatus


def build(seed=42, prob=0.3, delivery=0, level=500):
    c = SimulationConfig(simulation_step_seconds=5)
    r = RandomSource(seed)
    s = StationSimulationState(1)
    s.add_tank(TankState(1, 1, 1, "T", 1000, level, level, 200, 100, 20, 0, "OK"))
    s.add_pump(PumpState(1, 1, 1, 1, "P", PumpStatus.IDLE, 42, 10, 20, 8))
    return TickEngine(
        config=c,
        clock=SimulationClock(c, datetime(2026, 1, 1, 18, tzinfo=timezone.utc)),
        sales_generator=SalesGenerator(random_source=r, demand_profile=DemandProfile()),
        tank_generator=TankGenerator(random_source=r),
        pump_generator=PumpGenerator(random_source=r),
        delivery_generator=DeliveryGenerator(random_source=r),
        validator=SimulationValidator(),
        fuel_codes_by_id={1: "DIESEL"},
        unit_prices_by_fuel={"DIESEL": 45},
        base_sale_probability=prob,
        automatic_delivery_probability=delivery,
    ), s


def test_tick_and_sales():
    e, s = build(prob=1)
    before = s.tanks[1].true_level_liters
    out = e.run_tick(s)
    assert (
        out.sequence_number == 1
        and out.tank_count == out.pump_count == 1
        and s.tanks[1].true_level_liters < before
        and "SALE_STARTED" in [x.event_type for x in out.events]
    )


def test_probability_zero_and_pause():
    e, s = build(prob=0)
    assert not e.run_tick(s).sale_results
    e.clock.pause()
    before = s.sequence_number
    with pytest.raises(ValueError):
        e.run_tick(s)
    assert s.sequence_number == before


def test_delivery_and_twenty_ticks():
    e, s = build(prob=0, delivery=1, level=100)
    assert e.run_tick(s).deliveries
    e, s = build()
    for _ in range(20):
        e.run_tick(s)
    assert s.sequence_number == 20 and all(
        0 <= x.true_level_liters <= x.capacity_liters for x in s.tanks.values()
    )


@pytest.mark.parametrize("value", [-1, 2])
def test_invalid_probabilities(value):
    with pytest.raises(ValueError):
        build(prob=value)
