"""Contract tests for the static new-simulation lifecycle endpoint."""

from datetime import timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import simulations
from app.api.dependencies import require_admin
from app.database import get_db
from app.main import app
from app.utils.datetime_utils import utc_now
from app.utils.enums import SimulationStatus


def test_start_new_route_is_registered_as_post_before_generic_run_route() -> None:
    """Prevent a future dynamic ``/{run_id}`` route from shadowing start-new."""

    simulations_include = next(
        route
        for route in app.routes
        if getattr(getattr(route, "original_router", None), "prefix", None) == "/simulations"
    )
    routes = list(simulations_include.original_router.routes)
    start_new_index = next(
        index
        for index, route in enumerate(routes)
        if getattr(route, "path", None) == "/simulations/start-new"
    )
    generic_run_index = next(
        index
        for index, route in enumerate(routes)
        if getattr(route, "path", None) == "/simulations/{run_id}"
    )

    assert routes[start_new_index].methods == {"POST"}
    assert start_new_index < generic_run_index


def test_post_start_new_creates_and_starts_a_fresh_run(monkeypatch) -> None:
    """The desktop URL must resolve to a fresh, first-tick simulation run."""

    class FakeDb:
        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            pass

        def expire_all(self) -> None:
            pass

    class FakeStationRepository:
        def __init__(self, _: object) -> None:
            pass

        def get(self, station_id: int) -> object:
            return SimpleNamespace(id=station_id, is_active=True)

    created: list[object] = []

    class FakeSimulationRunRepository:
        def __init__(self, _: object) -> None:
            pass

        def create(self, values: dict[str, object]) -> object:
            now = utc_now()
            run = SimpleNamespace(
                id=902,
                target_simulation_time=None,
                progress_percent=None,
                real_started_at=None,
                real_ended_at=None,
                last_error=None,
                created_at=now,
                updated_at=now,
                **values,
            )
            created.append(run)
            return run

    class FakeManager:
        stopped_station_ids: list[int] = []
        started_run_ids: list[int] = []

        async def stop_active_realtime_run(self, station_id: int) -> None:
            self.stopped_station_ids.append(station_id)

        async def start_run(self, run_id: int) -> None:
            self.started_run_ids.append(run_id)
            run = created[0]
            run.status = SimulationStatus.RUNNING
            run.sequence_number = 1
            run.current_simulation_time = run.simulation_start_time + timedelta(
                seconds=run.simulation_step_seconds
            )

    manager = FakeManager()
    monkeypatch.setattr(simulations, "StationRepository", FakeStationRepository)
    monkeypatch.setattr(simulations, "SimulationRunRepository", FakeSimulationRunRepository)
    monkeypatch.setattr(simulations, "_get_run", lambda _, run_id: next(run for run in created if run.id == run_id))

    app.dependency_overrides[get_db] = lambda: FakeDb()
    app.dependency_overrides[simulations.get_simulation_manager] = lambda: manager
    app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id=17)
    try:
        with TestClient(app) as client:
            response = client.post("/api/simulations/start-new", json={"station_id": 7})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 902
    assert body["sequence_number"] == 1
    assert body["generated_sensor_count"] == 0
    assert body["generated_sale_count"] == 0
    assert body["generated_delivery_count"] == 0
    assert manager.stopped_station_ids == [7]
    assert manager.started_run_ids == [902]
