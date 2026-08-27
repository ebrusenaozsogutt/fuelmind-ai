"""Inventory projection and deterministic replenishment recommendations."""

from __future__ import annotations
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.exceptions import NotFoundError, BusinessRuleError
from app.models.forecast import Forecast
from app.models.order_recommendation import OrderRecommendation
from app.models.tank import Tank
from app.utils.enums import RecommendationPriority, RecommendationStatus


_TURKISH_MONTHS = ("", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")


def _format_liters(value: float) -> str:
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + " L"


def _format_date(value: object) -> str:
    return f"{value.day} {_TURKISH_MONTHS[value.month]} {value.year}"


class OrderPlanningService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate(self, tank_id: int) -> OrderRecommendation:
        tank = self.db.get(Tank, tank_id)
        if tank is None:
            raise NotFoundError("Tank not found.")
        forecasts = self._forecasts(tank)
        if len(forecasts) != 7:
            raise BusinessRuleError("A current seven-day forecast is required.")
        demands = [float(x.predicted_demand) for x in forecasts]
        current, minimum, capacity = map(
            float,
            (tank.current_level_liters, tank.minimum_safe_level, tank.capacity_liters),
        )
        opening, critical = current, None
        for item, demand in zip(forecasts, demands):
            closing = opening - demand
            if critical is None and closing < minimum:
                critical = item.forecast_date
            opening = closing
        total, average = sum(demands), sum(demands) / len(demands)
        safety = max(0.0, average * settings.SAFETY_STOCK_DAYS)
        available = max(0.0, current - minimum)
        ideal, receivable = (
            total + safety - available,
            max(0.0, capacity - current),
        )
        quantity = min(max(0.0, ideal), receivable)
        today = forecasts[0].forecast_date - timedelta(days=1)
        order_date = (
            today
            if critical is None
            else max(today, critical - timedelta(days=settings.DELIVERY_LEAD_TIME_DAYS))
        )
        delivery = order_date + timedelta(days=settings.DELIVERY_LEAD_TIME_DAYS)
        days = None if critical is None else (critical - today).days
        priority = (
            RecommendationPriority.LOW
            if quantity == 0
            else (
                RecommendationPriority.CRITICAL
                if days is not None and days <= settings.DELIVERY_LEAD_TIME_DAYS
                else RecommendationPriority.HIGH
                if days is not None and days <= settings.DELIVERY_LEAD_TIME_DAYS + 1
                else RecommendationPriority.MEDIUM
            )
        )
        confidence = sum(float(x.confidence_score) for x in forecasts) / len(forecasts)
        critical_text = _format_date(critical) if critical is not None else "tahmin ufku içinde beklenmiyor"
        explanation = (
            f"Mevcut stok {_format_liters(current)}'dir.\n"
            f"Minimum güvenli stok seviyesi {_format_liters(minimum)}'dir.\n"
            f"Önümüzdeki 7 gün için toplam {_format_liters(total)} tüketim tahmin edilmektedir.\n"
            f"Güvenlik stoğu {_format_liters(safety)} olarak hesaplanmıştır.\n"
            f"Tankın {critical_text} kritik seviyenin altına düşmesi beklenmektedir.\n"
            f"Bu nedenle {_format_date(order_date)} tarihinde {_format_liters(quantity)} sipariş verilmesi önerilir.\n"
            f"Tahmin güven skoru %{confidence:.2f}."
        )
        if ideal > receivable:
            explanation += f" Sipariş miktarı, tankın {_format_liters(receivable)} boş kapasitesiyle sınırlandırılmıştır."
        if quantity == 0:
            explanation = (
                "Sipariş gerekmiyor. Mevcut stok ve 7 günlük talep tahmini, "
                "minimum güvenli stok seviyesini korumaya yeterlidir. "
                f"Güvenlik stoğu {_format_liters(safety)} olarak hesaplanmıştır."
            )
        existing = self.db.scalar(
            select(OrderRecommendation)
            .where(
                OrderRecommendation.tank_id == tank.id,
                OrderRecommendation.status == RecommendationStatus.NEW,
            )
            .order_by(OrderRecommendation.created_at.desc())
        )
        values = dict(
            station_id=tank.station_id,
            tank_id=tank.id,
            recommended_order_date=order_date,
            recommended_delivery_date=delivery,
            recommended_quantity=Decimal(str(quantity)),
            critical_stock_date=critical,
            confidence_score=Decimal(str(confidence)),
            priority=priority,
            status=RecommendationStatus.NEW,
            explanation=explanation,
        )
        if existing is None:
            existing = OrderRecommendation(**values)
            self.db.add(existing)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
        self.db.commit()
        self.db.refresh(existing)
        return existing

    def latest(self, tank_id: int) -> OrderRecommendation:
        item = self.db.scalar(
            select(OrderRecommendation)
            .where(OrderRecommendation.tank_id == tank_id)
            .order_by(OrderRecommendation.created_at.desc())
        )
        if item is None:
            raise NotFoundError("Order recommendation not found.")
        return item

    def _forecasts(self, tank: Tank) -> list[Forecast]:
        rows = list(
            self.db.scalars(
                select(Forecast)
                .where(
                    Forecast.station_id == tank.station_id,
                    Forecast.fuel_type_id == tank.fuel_type_id,
                )
                .order_by(Forecast.created_at.desc(), Forecast.id.desc())
            )
        )
        if not rows:
            return []
        version = rows[0].model_version
        return sorted(
            [x for x in rows if x.model_version == version],
            key=lambda x: x.forecast_date,
        )[:7]
