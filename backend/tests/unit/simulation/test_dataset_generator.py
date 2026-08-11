"""Acceptance coverage for bounded 90-day dataset execution."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.simulation.dataset_generator import DatasetGenerator
from app.simulation.delivery_generator import DeliveryGenerator
from app.simulation.demand_profile import DemandProfile
from app.simulation.pump_generator import PumpGenerator
from app.simulation.random_source import RandomSource
from app.simulation.sales_generator import SalesGenerator
from app.simulation.clock import SimulationClock
from app.simulation.config import SimulationConfig
from app.simulation.state import PumpState, StationSimulationState, TankState
from app.simulation.tank_generator import TankGenerator
from app.simulation.tick_engine import TickEngine
from app.simulation.validators import SimulationValidator
from app.utils.enums import PumpStatus, SimulationStatus


@pytest.mark.asyncio
async def test_ninety_day_five_minute_execution_is_bounded_and_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    config = SimulationConfig(simulation_step_seconds=300)
    random_source = RandomSource(42)
    state = StationSimulationState(1)
    state.add_tank(TankState(1, 1, 1, "T1", 1_000_000, 900_000, 900_000, 200, 100, 20, 0, "OK"))
    state.add_pump(PumpState(1, 1, 1, 1, "P1", PumpStatus.IDLE, 42, 10, 20, 8))
    engine = TickEngine(
        config=config,
        clock=SimulationClock(config, start),
        sales_generator=SalesGenerator(random_source=random_source, demand_profile=DemandProfile()),
        tank_generator=TankGenerator(random_source=random_source),
        pump_generator=PumpGenerator(random_source=random_source),
        delivery_generator=DeliveryGenerator(random_source=random_source),
        validator=SimulationValidator(),
        fuel_codes_by_id={1: "DIESEL"}, unit_prices_by_fuel={"DIESEL": 45},
        base_sale_probability=0, automatic_delivery_probability=0,
    )
    generator = DatasetGenerator(runner=SimpleNamespace(run_id=99, station_state=state, tick_engine=engine), days=90)
    batches: list[int] = []
    statuses: list[SimulationStatus] = []
    yields: list[int] = []

    def persist(results: list[object]) -> None:
        batches.append(len(results))

    async def set_status(status: SimulationStatus, **_: object) -> None:
        statuses.append(status)

    original_sleep = asyncio.sleep

    async def sleep(delay: float) -> None:
        yields.append(int(delay))
        await original_sleep(delay)

    monkeypatch.setattr(generator, "_persist", persist)
    monkeypatch.setattr(generator, "_set_status", set_status)
    monkeypatch.setattr("app.simulation.dataset_generator.asyncio.sleep", sleep)

    await generator.generate()

    assert sum(batches) == 25_920
    assert batches == [100] * 259 + [20]
    assert max(batches) == 100
    assert yields == [0] * 259
    assert state.sequence_number == 25_920
    assert engine.clock.current_time == start + timedelta(days=90)
    assert statuses == [SimulationStatus.STARTING, SimulationStatus.RUNNING, SimulationStatus.COMPLETED]
