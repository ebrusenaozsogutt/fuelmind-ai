"""Authorization and error contracts for recommendation endpoints."""

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.exceptions import BusinessRuleError, NotFoundError
from app.main import app
from app.schemas.tank import OrderRecommendationRead
from app.utils.enums import RecommendationPriority, RecommendationStatus
from datetime import date
from decimal import Decimal
from types import SimpleNamespace


def request(path, method="get"):
    with TestClient(app) as client:
        return getattr(client, method)(path)


def test_generate_requires_admin_and_get_allows_operator() -> None:
    app.dependency_overrides[require_admin] = lambda: (_ for _ in ()).throw(HTTPException(403, "forbidden"))
    try:
        assert request("/api/tanks/1/recommendation/generate", "post").status_code == 403
    finally:
        app.dependency_overrides.clear()
    assert request("/api/tanks/1/recommendation/generate", "post").status_code == 401
    app.dependency_overrides[require_operator_or_admin] = lambda: (_ for _ in ()).throw(HTTPException(403, "forbidden"))
    try:
        assert request("/api/tanks/1/recommendation").status_code == 403
    finally:
        app.dependency_overrides.clear()
    assert request("/api/tanks/1/recommendation").status_code == 401


def test_recommendation_error_mapping(monkeypatch) -> None:
    class FailingService:
        def __init__(self, _db):
            pass

        def generate(self, tank_id):
            if tank_id == 404:
                raise NotFoundError("Tank not found.")
            raise BusinessRuleError("A current seven-day forecast is required.")

        def latest(self, _tank_id):
            raise NotFoundError("Order recommendation not found.")

    monkeypatch.setattr("app.api.tanks.OrderPlanningService", FailingService)
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[require_admin] = lambda: object()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    try:
        assert request("/api/tanks/404/recommendation/generate", "post").status_code == 404
        assert request("/api/tanks/1/recommendation/generate", "post").status_code == 400
        assert request("/api/tanks/1/recommendation").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_recommendation_response_contract_serializes_orm_values() -> None:
    payload = OrderRecommendationRead.model_validate(
        SimpleNamespace(
            tank_id=3,
            station_id=2,
            current_stock_liters=Decimal("6190.946"),
            minimum_safe_stock_liters=Decimal("6250.000"),
            recommended_quantity=Decimal("0.000"),
            recommended_order_date=date(2026, 12, 3),
            recommended_delivery_date=date(2026, 12, 5),
            critical_stock_date=None,
            confidence_score=Decimal("91.18"),
            priority=RecommendationPriority.LOW,
            status=RecommendationStatus.NEW,
            explanation="Sipariş gerekmiyor.",
        )
    )

    assert payload.model_dump(mode="json") == {
        "tank_id": 3,
        "station_id": 2,
        "current_stock_liters": "6190.946",
        "minimum_safe_stock_liters": "6250.000",
        "recommended_quantity": "0.000",
        "recommended_order_date": "2026-12-03",
        "recommended_delivery_date": "2026-12-05",
        "critical_stock_date": None,
        "confidence_score": "91.18",
        "priority": "LOW",
        "status": "NEW",
        "explanation": "Sipariş gerekmiyor.",
    }
