"""End-to-end acceptance for persisted realtime ticks over the live socket."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import live
from app.api.dependencies import require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.delivery import Delivery
from app.models.fuel_type import FuelType
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.sensor_reading import SensorReading
from app.models.simulation_event import SimulationEvent
from app.models.simulation_run import SimulationRun
from app.models.station import Station
from app.models.tank import Tank
from app.repositories.simulation_run_repository import SimulationRunRepository
from app.simulation.dependencies import build_simulation_runner
from app.utils.datetime_utils import utc_now
from app.utils.enums import PumpStatus, SimulationMode, SimulationStatus

_TABLES = [
    FuelType.__table__,
    Station.__table__,
    Tank.__table__,
    Pump.__table__,
    SimulationRun.__table__,
    SensorReading.__table__,
    Sale.__table__,
    Delivery.__table__,
    SimulationEvent.__table__,
]


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_: JSONB, __, **___) -> str:
    """Keep the isolated test DB compatible with the production JSONB model."""

    return "JSON"


def _receive_tick(websocket):
    """Read a bounded number of frames, ignoring an incidental heartbeat ping."""

    for _ in range(5):
        message = websocket.receive_json()
        if message["event_type"] == "simulation_tick":
            return message
    raise AssertionError("Timed out waiting for a simulation_tick frame.")


async def _wait_for_sequence(factory, run_id: int, minimum: int) -> int:
    for _ in range(100):
        session = factory()
        try:
            sequence = SimulationRunRepository(session).get(run_id).sequence_number
        finally:
            session.close()
        if sequence >= minimum:
            return sequence
        await asyncio.sleep(0.01)
    raise AssertionError(f"Run {run_id} did not reach sequence {minimum}.")


async def _wait_for_connection_count(
    station_id: int, expected_count: int, *, timeout_seconds: float = 1.0
) -> None:
    """Wait for the ASGI receive loop to process a client close frame."""

    manager = app.state.connection_manager
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while manager.connection_count(station_id) != expected_count:
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(
                f"Expected {expected_count} station connections, found "
                f"{manager.connection_count(station_id)}."
            )
        await asyncio.sleep(0.01)


def test_realtime_runner_socket_disconnect_reconnect_and_history_backfill(monkeypatch) -> None:
    """Prove the production runner path survives a live-client disconnect."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    fuel = FuelType(name="Diesel", code="DIESEL")
    station = Station(code="WS-1", name="Socket", city="A", district="A", address="A")
    session.add_all([fuel, station])
    session.flush()
    tank = Tank(
        station_id=station.id,
        fuel_type_id=fuel.id,
        code="T-1",
        capacity_liters=Decimal("1000"),
        current_level_liters=Decimal("700"),
        minimum_safe_level=Decimal("100"),
        critical_level=Decimal("50"),
    )
    session.add(tank)
    session.flush()
    session.add(
        Pump(
            station_id=station.id,
            tank_id=tank.id,
            code="P-1",
            status=PumpStatus.IDLE,
            nominal_flow_rate=Decimal("20"),
            minimum_flow_rate=Decimal("1"),
            maximum_motor_current=Decimal("10"),
            maximum_pressure=Decimal("10"),
        )
    )
    run = SimulationRun(
        station_id=station.id,
        status=SimulationStatus.CREATED,
        mode=SimulationMode.REALTIME,
        simulation_start_time=utc_now() - timedelta(minutes=1),
        tick_interval_ms=10,
        simulation_step_seconds=1,
        speed_multiplier=1,
        random_seed=7,
        persist_every_n_ticks=1,
    )
    session.add(run)
    session.commit()
    run_id, station_id = run.id, station.id
    session.close()

    monkeypatch.setattr(live, "SessionLocal", factory)
    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    runner = None
    task = None
    client = TestClient(app)
    client.__enter__()
    try:
        if True:
            with client.websocket_connect(f"/api/ws/stations/{station_id}/live") as socket:
                ready = socket.receive_json()
                assert ready["event_type"] == "connection_ready"
                assert ready["station_id"] == station_id
                runner = build_simulation_runner(
                    run_id,
                    session_factory=factory,
                    live_event_broker=app.state.live_event_broker,
                )
                task = client.portal.start_task_soon(runner.start)
                client.portal.call(runner.wait_until_started)
                first, second = _receive_tick(socket), _receive_tick(socket)
                assert first["simulation_run_id"] == run_id
                assert first["station_id"] == station_id
                assert {"sequence", "simulation_time", "tanks", "pumps", "sales", "events", "active_scenarios", "generated_at"} <= first.keys()
                assert second["sequence"] == first["sequence"] + 1
            client.portal.call(_wait_for_connection_count, station_id, 0)
            before_disconnect = second["sequence"]
            continued = client.portal.call(_wait_for_sequence, factory, run_id, before_disconnect + 2)
            assert runner.status != SimulationStatus.FAILED
            with client.websocket_connect(f"/api/ws/stations/{station_id}/live") as replacement:
                assert replacement.receive_json()["event_type"] == "connection_ready"
                assert app.state.connection_manager.connection_count(station_id) == 1
                backfill = client.get(
                    f"/api/stations/{station_id}/sensor-history",
                    params={
                        "from": datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat(),
                        "to": datetime(2030, 1, 1, tzinfo=timezone.utc).isoformat(),
                        "limit": 5000,
                    },
                )
            assert backfill.status_code == 200
            history = [item for item in backfill.json() if item["simulation_run_id"] == run_id]
            sequences = [item["sequence_number"] for item in history]
            assert sequences == sorted(sequences)
            assert any(sequence > before_disconnect for sequence in sequences)
            assert max(sequences) >= continued
            with client.websocket_connect(f"/api/ws/stations/{station_id}/live") as resumed_socket:
                assert resumed_socket.receive_json()["event_type"] == "connection_ready"
                resumed = _receive_tick(resumed_socket)
                assert resumed["sequence"] > continued
            client.portal.call(runner.stop)
            task.result(timeout=2)
            task = None
    finally:
        if runner is not None and task is not None:
            client.portal.call(runner.stop)
            task.result(timeout=2)
        client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()
