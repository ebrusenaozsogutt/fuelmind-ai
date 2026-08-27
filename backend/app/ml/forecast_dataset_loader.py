"""Read completed sales as stable raw input for the forecasting pipeline.

This module intentionally does not aggregate rows or derive features.  Those
responsibilities belong to later forecasting stages; keeping this boundary raw
makes price and relationship snapshots auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sale import Sale
from app.utils.enums import PaymentType, SaleStatus
from app.utils.enums import AnomalyType


@dataclass(frozen=True)
class ForecastRawSale:
    """One completed sale with the snapshots needed by downstream forecasting."""

    sale_id: int
    simulation_sale_id: str | None
    simulation_run_id: int | None
    station_id: int
    tank_id: int
    pump_id: int
    nozzle_id: int | None
    fuel_type_id: int
    customer_id: int | None
    vehicle_id: int | None
    fuel_card_id: int | None
    attendant_id: int | None
    shift_id: int | None
    sale_timestamp: datetime
    quantity_liters: Decimal
    unit_price: Decimal
    total_amount: Decimal
    start_totalizer_liters: Decimal | None
    end_totalizer_liters: Decimal | None
    payment_type: PaymentType | None
    sale_status: SaleStatus
    is_anomaly: bool
    anomaly_type: AnomalyType | None


class ForecastRawDatasetLoader:
    """Query only chronological, completed raw sales for forecast training."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def load(
        self,
        *,
        station_id: int | None = None,
        start_at: date | datetime | None = None,
        end_at: date | datetime | None = None,
    ) -> list[ForecastRawSale]:
        """Return timestamp-ordered sales in ``[start_at, end_at)``.

        ``date`` values mean midnight UTC.  Datetime boundaries must be aware
        so a caller cannot silently mix simulation history with local time.
        """

        if station_id is not None and station_id <= 0:
            raise ValueError("station_id must be positive.")
        start = self._boundary(start_at, "start_at")
        end = self._boundary(end_at, "end_at")
        if start is not None and end is not None and end < start:
            raise ValueError("end_at cannot precede start_at.")

        statement = select(Sale).where(Sale.sale_status == SaleStatus.COMPLETED)
        if station_id is not None:
            statement = statement.where(Sale.station_id == station_id)
        if start is not None:
            statement = statement.where(Sale.sale_timestamp >= start)
        if end is not None:
            statement = statement.where(Sale.sale_timestamp < end)
        rows = self.db.scalars(statement.order_by(Sale.sale_timestamp, Sale.id))
        return [self._row(sale) for sale in rows]

    @staticmethod
    def _boundary(value: date | datetime | None, name: str) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must include a timezone.")
            return value.astimezone(timezone.utc)
        return datetime.combine(value, time.min, tzinfo=timezone.utc)

    @staticmethod
    def _row(sale: Sale) -> ForecastRawSale:
        return ForecastRawSale(
            sale_id=sale.id,
            simulation_sale_id=sale.simulation_sale_id,
            simulation_run_id=sale.simulation_run_id,
            station_id=sale.station_id,
            tank_id=sale.tank_id,
            pump_id=sale.pump_id,
            nozzle_id=sale.nozzle_id,
            fuel_type_id=sale.fuel_type_id,
            customer_id=sale.customer_id,
            vehicle_id=sale.vehicle_id,
            fuel_card_id=sale.fuel_card_id,
            attendant_id=sale.attendant_id,
            shift_id=sale.shift_id,
            sale_timestamp=sale.sale_timestamp,
            quantity_liters=sale.quantity_liters,
            unit_price=sale.unit_price,
            total_amount=sale.total_amount,
            start_totalizer_liters=sale.start_totalizer_liters,
            end_totalizer_liters=sale.end_totalizer_liters,
            payment_type=sale.payment_type,
            sale_status=sale.sale_status,
            is_anomaly=sale.is_anomaly,
            anomaly_type=sale.anomaly_type,
        )
