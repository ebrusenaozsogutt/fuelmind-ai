"""API-level CRUD coverage for run-owned simulation scenarios."""

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import simulations
from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.main import app
from app.utils.enums import SimulationStatus


class FakeSession:
    def commit(self): pass
    def rollback(self): pass
    def refresh(self, _: object): pass


def test_scenario_crud_is_scoped_to_run(monkeypatch):
    store = []
    run = SimpleNamespace(id=7, station_id=10)

    class Runs:
        def __init__(self, _: object): pass
        def get(self, run_id): return run if run_id == 7 else None

    class Scenarios:
        def __init__(self, _: object): pass
        def create(self, values):
            entity = SimpleNamespace(id=3, created_at=datetime.now(timezone.utc), **values)
            store.append(entity)
            return entity
        def list_for_run(self, run_id): return [x for x in store if x.simulation_run_id == run_id]
        def get_for_run(self, run_id, scenario_id):
            return next((x for x in store if x.simulation_run_id == run_id and x.id == scenario_id), None)
        def delete(self, entity): store.remove(entity)

    monkeypatch.setattr(simulations, "SimulationRunRepository", Runs)
    monkeypatch.setattr(simulations, "SimulationScenarioRepository", Scenarios)
    app.dependency_overrides[get_db] = lambda: FakeSession()
    app.dependency_overrides[require_admin] = lambda: object()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    payload = {"name": "Demand", "scenario_type": "DEMAND_SURGE", "target_type": "STATION",
               "target_id": 10, "start_time": "2026-01-01T00:00:00+00:00", "duration_minutes": 5}
    try:
        with TestClient(app) as client:
            created = client.post("/api/simulations/7/scenarios", json=payload)
            listed = client.get("/api/simulations/7/scenarios")
            deleted = client.delete("/api/simulations/7/scenarios/3")
    finally:
        app.dependency_overrides.clear()
    assert created.status_code == 201
    assert created.json()["status"] == SimulationStatus.CREATED.value
    assert [item["id"] for item in listed.json()] == [3]
    assert deleted.status_code == 204 and store == []
