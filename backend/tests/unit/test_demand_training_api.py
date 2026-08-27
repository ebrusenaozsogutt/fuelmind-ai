"""Authorization and response contract for demand-model training."""

from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import require_admin
from app.database import get_db
from app.main import app


def test_train_demand_model_requires_admin_and_returns_training_summary(monkeypatch) -> None:
    class FakeService:
        def __init__(self, db):
            assert db == "db"

        def train(self, **kwargs):
            assert kwargs == {"station_id": 1, "start_at": None, "end_at": None}
            evaluation = SimpleNamespace(mae=1.0, rmse=2.0, mape=3.0, train_row_count=12, test_row_count=3)
            return SimpleNamespace(
                baseline=evaluation, xgboost=evaluation, winner="xgboost",
                registry_record=SimpleNamespace(version="v0001", is_active=True),
            )

    monkeypatch.setattr("app.api.models.DemandTrainingService", FakeService)
    app.dependency_overrides[get_db] = lambda: "db"
    app.dependency_overrides[require_admin] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.post("/api/ml/train-demand-model", json={"station_id": 1})
        assert response.status_code == 201
        assert response.json()["winner"] == "xgboost"
    finally:
        app.dependency_overrides.clear()


def test_train_demand_model_rejects_operator_and_anonymous() -> None:
    app.dependency_overrides[require_admin] = lambda: (_ for _ in ()).throw(HTTPException(403, "forbidden"))
    try:
        with TestClient(app) as client:
            assert client.post("/api/ml/train-demand-model", json={}).status_code == 403
    finally:
        app.dependency_overrides.clear()
    with TestClient(app) as client:
        assert client.post("/api/ml/train-demand-model", json={}).status_code == 401
