"""Acceptance coverage for the existing order-planning calculation."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services.order_planning_service import OrderPlanningService
from app.utils.enums import RecommendationPriority, RecommendationStatus


TODAY = date(2026, 8, 25)


def forecast(day: int, demand: float, confidence: float = 80.0):
    return SimpleNamespace(
        id=day,
        forecast_date=TODAY + timedelta(days=day),
        predicted_demand=Decimal(str(demand)),
        confidence_score=Decimal(str(confidence)),
        model_version="acceptance-v1",
        created_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )


class PlanningSession:
    """Small in-memory session boundary; calculations still use production service."""

    def __init__(self, tank, forecasts, existing=None):
        self.tank, self.forecast_rows, self.existing = tank, forecasts, existing
        self.added = []

    def get(self, _model, _id):
        return self.tank if _id == self.tank.id else None

    def scalars(self, _statement):
        return iter(self.forecast_rows)

    def scalar(self, _statement):
        return self.existing

    def add(self, item):
        self.added.append(item)
        self.existing = item

    def commit(self):
        pass

    def refresh(self, _item):
        pass


def tank(*, stock=1000, minimum=300, capacity=3000):
    return SimpleNamespace(
        id=1, station_id=2, fuel_type_id=3,
        current_level_liters=Decimal(str(stock)),
        minimum_safe_level=Decimal(str(minimum)),
        capacity_liters=Decimal(str(capacity)),
    )


def generate(*, stock=1000, minimum=300, capacity=3000, demands=(200,) * 7,
             confidences=None, existing=None):
    rows = [forecast(i + 1, value, (confidences or [80] * 7)[i]) for i, value in enumerate(demands)]
    return OrderPlanningService(PlanningSession(tank(stock=stock, minimum=minimum, capacity=capacity), rows, existing)).generate(1)


def test_critical_stock_is_first_day_strictly_below_minimum() -> None:
    recommendation = generate(demands=(200, 250, 300, 0, 0, 0, 0))
    assert recommendation.critical_stock_date == TODAY + timedelta(days=3)


def test_stock_equal_to_minimum_is_not_critical() -> None:
    recommendation = generate(stock=1000, minimum=300, demands=(700, 1, 0, 0, 0, 0, 0))
    assert recommendation.critical_stock_date == TODAY + timedelta(days=2)


def test_no_critical_stock_within_forecast_horizon() -> None:
    recommendation = generate(stock=3000, minimum=300, capacity=4000, demands=(100,) * 7)
    assert recommendation.critical_stock_date is None


def test_safety_stock_uses_two_days_and_never_negative() -> None:
    recommendation = generate(demands=(100,) * 7)
    assert "Güvenlik stoğu 200,00 L" in recommendation.explanation
    zero = generate(stock=100, minimum=0, demands=(0,) * 7)
    assert "Güvenlik stoğu 0,00 L" in zero.explanation


def test_quantity_follows_available_stock_formula_and_capacity_clamp() -> None:
    recommendation = generate(stock=1000, minimum=300, capacity=1200, demands=(200,) * 7)
    # 1400 + (200 * settings.SAFETY_STOCK_DAYS) - 700 = 1100; only 200 L fits.
    assert float(recommendation.recommended_quantity) == 200
    assert "tankın 200,00 L boş kapasitesiyle" in recommendation.explanation


def test_full_tank_cannot_produce_negative_capacity_or_order() -> None:
    recommendation = generate(stock=1000, minimum=300, capacity=1000, demands=(10,) * 7)
    assert recommendation.recommended_quantity == 0
    assert recommendation.priority is RecommendationPriority.LOW


def test_no_order_contract_has_low_priority_no_critical_date_and_explanation() -> None:
    recommendation = generate(stock=3000, minimum=300, capacity=4000, demands=(100,) * 7)
    assert recommendation.recommended_quantity == 0
    assert recommendation.priority is RecommendationPriority.LOW
    assert recommendation.critical_stock_date is None
    assert "Sipariş gerekmiyor" in recommendation.explanation
    assert recommendation.recommended_delivery_date == recommendation.recommended_order_date + timedelta(days=settings.DELIVERY_LEAD_TIME_DAYS)


@pytest.mark.parametrize(
    ("demands", "expected"),
    [((800, 0, 0, 0, 0, 0, 0), RecommendationPriority.CRITICAL),
     ((200, 200, 400, 0, 0, 0, 0), RecommendationPriority.HIGH),
     ((200, 200, 200, 200, 0, 0, 0), RecommendationPriority.MEDIUM)],
)
def test_priority_rules(demands, expected) -> None:
    assert generate(demands=demands).priority is expected


def test_dates_confidence_and_explanation_are_derived_from_forecasts() -> None:
    recommendation = generate(demands=(200, 250, 300, 0, 0, 0, 0), confidences=[50, 60, 70, 80, 90, 100, 100])
    assert recommendation.recommended_order_date == TODAY + timedelta(days=1)
    assert recommendation.recommended_delivery_date == TODAY + timedelta(days=1 + settings.DELIVERY_LEAD_TIME_DAYS)
    assert float(recommendation.confidence_score) == pytest.approx(550 / 7)
    assert 0 <= float(recommendation.confidence_score) <= 100
    for phrase in ("Mevcut stok", "Minimum güvenli stok seviyesi", "Önümüzdeki 7 gün", "Güvenlik stoğu", "sipariş verilmesi önerilir", "kritik seviyenin altına"):
        assert phrase in recommendation.explanation


def test_existing_new_recommendation_is_updated_without_duplicate() -> None:
    existing = SimpleNamespace(status=RecommendationStatus.NEW, created_at=datetime.now(timezone.utc))
    recommendation = generate(existing=existing)
    assert recommendation is existing
    assert recommendation.status is RecommendationStatus.NEW
    assert recommendation.tank_id == 1
