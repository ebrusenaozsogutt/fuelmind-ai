"""Authorization and controlled-error contracts for forecast endpoints."""

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import require_admin
from app.database import get_db
from app.main import app
from app.services.forecast_generation_service import DemandForecastArtifactError


def test_generate_requires_admin() -> None:
    app.dependency_overrides[require_admin] = lambda: (_ for _ in ()).throw(HTTPException(403, "forbidden"))
    try:
        with TestClient(app) as client:
            assert client.post("/api/forecasts/generate?station_id=1").status_code == 403
    finally:
        app.dependency_overrides.clear()
    with TestClient(app) as client:
        assert client.post("/api/forecasts/generate?station_id=1").status_code == 401


def test_generate_returns_controlled_artifact_error(monkeypatch) -> None:
    class FailingService:
        def __init__(self, _db) -> None:
            pass

        def generate(self, *_args):
            raise DemandForecastArtifactError("artifact unavailable")

    monkeypatch.setattr("app.api.forecasts.ForecastGenerationService", FailingService)
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[require_admin] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.post("/api/forecasts/generate?station_id=1")
        assert response.status_code == 503
        assert response.json()["error"]["message"] == "artifact unavailable"
    finally:
        app.dependency_overrides.clear()
