"""Unit tests for isolated live tick publishing."""

from datetime import datetime, timezone

import pytest

from app.live.event_broker import LiveEventBroker
from app.simulation.tick_result import SimulationTickResult


class FakeConnectionManager:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.calls: list[tuple[int, dict[str, object]]] = []

    async def broadcast(self, station_id: int, message: dict[str, object]) -> None:
        if self.fails:
            raise RuntimeError("closed websocket")
        self.calls.append((station_id, message))


@pytest.mark.asyncio
async def test_broker_serializes_and_broadcasts_to_tick_station() -> None:
    manager = FakeConnectionManager()
    tick = SimulationTickResult(2, datetime(2026, 8, 7, tzinfo=timezone.utc), 51)

    await LiveEventBroker(manager).publish_simulation_tick(15, tick)  # type: ignore[arg-type]

    station_id, payload = manager.calls[0]
    assert station_id == 2
    assert payload["event_type"] == "simulation_tick"
    assert payload["simulation_run_id"] == 15
    assert payload["sequence"] == 51


@pytest.mark.asyncio
async def test_broker_swallows_transport_failure_and_no_client_is_a_noop() -> None:
    tick = SimulationTickResult(2, datetime(2026, 8, 7, tzinfo=timezone.utc), 1)

    await LiveEventBroker(FakeConnectionManager(fails=True)).publish_simulation_tick(1, tick)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_sequence_drops_duplicate_and_out_of_order_but_keeps_gap_and_new_run() -> None:
    manager = FakeConnectionManager()
    broker = LiveEventBroker(manager)  # type: ignore[arg-type]
    moment = datetime(2026, 8, 7, tzinfo=timezone.utc)

    for sequence in (10, 10, 9, 13):
        await broker.publish_simulation_tick(1, SimulationTickResult(2, moment, sequence))
    await broker.publish_simulation_tick(2, SimulationTickResult(2, moment, 1))

    assert [payload["sequence"] for _, payload in manager.calls] == [10, 13, 1]


@pytest.mark.asyncio
async def test_new_run_first_websocket_tick_has_its_own_run_id_and_sequence() -> None:
    """A new run's sequence one is never rejected as an old run duplicate."""

    manager = FakeConnectionManager()
    broker = LiveEventBroker(manager)  # type: ignore[arg-type]
    moment = datetime(2026, 8, 1, tzinfo=timezone.utc)

    await broker.publish_simulation_tick(41, SimulationTickResult(2, moment, 10))
    await broker.publish_simulation_tick(42, SimulationTickResult(2, moment, 1))

    assert manager.calls[-1][1]["simulation_run_id"] == 42
    assert manager.calls[-1][1]["sequence"] == 1
