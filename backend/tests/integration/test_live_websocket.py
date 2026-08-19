"""Integration coverage for the station live WebSocket endpoint."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import live
from app.main import app
from app.services.live_topology_service import (
    LiveTopologySnapshot,
    NozzleLiveState,
    ProbeLiveState,
)
from app.simulation.field_device import ProbeObservation
from app.simulation.tick_result import SimulationTickResult
from app.utils.enums import NozzleStatus, ProbeStatus


async def _wait_for_connection_count(
    station_id: int, expected_count: int, *, timeout_seconds: float = 1.0
) -> None:
    """Wait until the ASGI receive loop has processed a WebSocket close frame."""

    manager = app.state.connection_manager
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while manager.connection_count(station_id) != expected_count:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(
                f"Expected {expected_count} station connections, found "
                f"{manager.connection_count(station_id)}."
            )
        await asyncio.sleep(0.01)


async def _publish_with_topology(tick, topology) -> None:
    await app.state.live_event_broker.publish_simulation_tick(
        3, tick, topology=topology
    )


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
            # TestClient cancels the ASGI task during context-manager teardown,
            # which can race the endpoint's receive-loop cleanup. Send the close
            # frame while that task is still active so this asserts real cleanup.
            websocket.close()
            client.portal.call(_wait_for_connection_count, 1, 0)


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


def test_live_websocket_emits_additive_field_topology(monkeypatch) -> None:
    monkeypatch.setattr(live, "_station_exists", lambda _: True)
    moment = datetime(2026, 8, 7, tzinfo=timezone.utc)
    tick = SimulationTickResult(
        1,
        moment,
        11,
        probe_observations=[
            ProbeObservation(9, 1, 1300, 650, 10, 5, 18.7, 98, ("OK",))
        ],
    )
    topology = LiveTopologySnapshot(
        probes=[ProbeLiveState(9, 1, None, "PRB-1", "Probe", ProbeStatus.ONLINE, True, None)],
        nozzles=[NozzleLiveState(7, 3, 2, "NZL-1", 1, NozzleStatus.AVAILABLE, 120, True, "DSL", "Diesel")],
        dispensing_nozzle_ids=frozenset({7}),
    )
    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/stations/1/live") as websocket:
            assert websocket.receive_json()["event_type"] == "connection_ready"
            client.portal.call(_publish_with_topology, tick, topology)
            payload = websocket.receive_json()
    assert payload["probes"][0]["fuel_volume_liters"] == 650
    assert payload["probes"][0]["quality_flags"] == ["OK"]
    assert payload["nozzles"][0]["status"] == "DISPENSING"


def test_live_websocket_serializes_persisted_field_topology_values(monkeypatch) -> None:
    """Decimal totalizers and topology timestamps must not disconnect a live client."""

    monkeypatch.setattr(live, "_station_exists", lambda _: True)
    moment = datetime(2026, 8, 7, tzinfo=timezone.utc)
    tick = SimulationTickResult(1, moment, 12)
    topology = LiveTopologySnapshot(
        probes=[
            ProbeLiveState(
                9, 1, None, "PRB-1", "Probe", ProbeStatus.ONLINE, True, moment
            )
        ],
        nozzles=[
            NozzleLiveState(
                7,
                3,
                2,
                "NZL-1",
                1,
                NozzleStatus.AVAILABLE,
                Decimal("125342.900"),
                True,
                "DSL",
                "Diesel",
            )
        ],
    )
    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/stations/1/live") as websocket:
            assert websocket.receive_json()["event_type"] == "connection_ready"
            client.portal.call(_publish_with_topology, tick, topology)
            payload = websocket.receive_json()

    assert payload["nozzles"][0]["totalizer_liters"] == 125342.9
    assert payload["probes"][0]["last_communication_at"] == moment.isoformat()


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
    asyncio.run(exercise())
