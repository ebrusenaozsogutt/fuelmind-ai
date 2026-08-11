"""Integration coverage for the station live WebSocket endpoint."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import live
from app.main import app
from app.simulation.tick_result import SimulationTickResult


def test_live_websocket_ready_publish_and_disconnect_cleanup(monkeypatch) -> None:
    monkeypatch.setattr(live, "_station_exists", lambda _: True)
    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/stations/1/live") as websocket:
            ready = websocket.receive_json()
            assert ready["event_type"] == "connection_ready"
            assert ready["station_id"] == 1
            assert app.state.connection_manager.connection_count(1) == 1
            tick = SimulationTickResult(
                1, datetime(2026, 8, 7, tzinfo=timezone.utc), 9
            )
            client.portal.call(app.state.live_event_broker.publish_simulation_tick, 3, tick)
            assert websocket.receive_json()["sequence"] == 9
        assert app.state.connection_manager.connection_count(1) == 0


def test_live_websocket_multiple_clients_share_channel(monkeypatch) -> None:
    monkeypatch.setattr(live, "_station_exists", lambda _: True)
    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/stations/1/live") as first:
            with client.websocket_connect("/api/ws/stations/1/live") as second:
                first.receive_json()
                second.receive_json()
                assert app.state.connection_manager.connection_count(1) == 2
                tick = SimulationTickResult(
                    1, datetime(2026, 8, 7, tzinfo=timezone.utc), 10
                )
                client.portal.call(app.state.live_event_broker.publish_simulation_tick, 3, tick)
                assert first.receive_json()["sequence"] == 10
                assert second.receive_json()["sequence"] == 10


def test_live_websocket_rejects_unknown_station(monkeypatch) -> None:
    monkeypatch.setattr(live, "_station_exists", lambda _: False)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/api/ws/stations/999/live"):
                pass
    assert error.value.code == 1008


def test_live_websocket_heartbeat_ping_pong_keeps_connection_alive(monkeypatch) -> None:
    """A short test interval proves ping follows ready and pong refreshes liveness."""

    monkeypatch.setattr(live, "_station_exists", lambda _: True)
    monkeypatch.setattr(live.settings, "LIVE_WS_HEARTBEAT_SECONDS", 0.02)
    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/stations/1/live") as websocket:
            assert websocket.receive_json()["event_type"] == "connection_ready"
            assert websocket.receive_json()["event_type"] == "ping"
            websocket.send_json({"event_type": "pong"})
            assert websocket.receive_json()["event_type"] == "ping"
            assert app.state.connection_manager.connection_count(1) == 1


def test_heartbeat_stale_cleanup_removes_only_stale_client(monkeypatch) -> None:
    """The heartbeat cleanup path removes its socket without touching a peer."""

    class Socket:
        async def accept(self) -> None:
            pass

        async def close(self, code: int) -> None:
            self.code = code

    async def exercise() -> None:
        manager = live.ConnectionManager()
        stale, healthy = Socket(), Socket()
        await manager.connect(1, stale)
        await manager.connect(1, healthy)
        manager._last_pong[stale] = datetime(2000, 1, 1, tzinfo=timezone.utc)
        await live._heartbeat(manager, 1, stale)
        assert manager.connection_count(1) == 1
        assert not manager.is_stale(healthy, 1)

    monkeypatch.setattr(live.settings, "LIVE_WS_HEARTBEAT_SECONDS", 0)
    import asyncio
    asyncio.run(exercise())
