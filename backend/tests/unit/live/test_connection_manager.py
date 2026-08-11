"""Unit coverage for station-scoped WebSocket connection management."""

import pytest

from app.live.connection_manager import ConnectionManager


class FakeWebSocket:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.accepted = False
        self.messages: list[dict[str, object]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, object]) -> None:
        if self.fails:
            raise RuntimeError("closed")
        self.messages.append(message)


@pytest.mark.asyncio
async def test_connects_multiple_clients_in_isolated_station_channels() -> None:
    manager = ConnectionManager()
    first, second, other = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()

    await manager.connect(1, first)
    await manager.connect(1, second)
    await manager.connect(2, other)

    assert first.accepted and second.accepted and other.accepted
    assert manager.connection_count(1) == 2
    assert manager.connection_count(2) == 1
    assert manager.total_connection_count() == 3


@pytest.mark.asyncio
async def test_disconnect_is_idempotent_and_cleans_empty_channel() -> None:
    manager = ConnectionManager()
    websocket = FakeWebSocket()

    await manager.connect(1, websocket)
    await manager.disconnect(1, websocket)
    await manager.disconnect(1, websocket)

    assert not manager.has_connections(1)
    assert manager.total_connection_count() == 0


@pytest.mark.asyncio
async def test_broadcast_only_targets_requested_station() -> None:
    manager = ConnectionManager()
    station_one, station_two = FakeWebSocket(), FakeWebSocket()
    await manager.connect(1, station_one)
    await manager.connect(2, station_two)

    await manager.broadcast(1, {"type": "tick", "sequence": 1})

    assert station_one.messages == [{"type": "tick", "sequence": 1}]
    assert station_two.messages == []


@pytest.mark.asyncio
async def test_broadcast_isolates_send_failure_and_removes_failed_client() -> None:
    manager = ConnectionManager()
    healthy, failed = FakeWebSocket(), FakeWebSocket(fails=True)
    await manager.connect(1, healthy)
    await manager.connect(1, failed)

    await manager.broadcast(1, {"type": "tick"})

    assert healthy.messages == [{"type": "tick"}]
    assert manager.connection_count(1) == 1
