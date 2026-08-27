"""Tank sales reconciliation using durable sale and delivery facts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import NotFoundError
from app.models.delivery import Delivery
from app.models.sale import Sale
from app.models.tank import Tank
from app.repositories.alarm_repository import AlarmRepository
from app.schemas.reconciliation import TankReconciliationRead
from app.services.alarm_engine import AlarmEngine, RuleAlarmCandidate
from app.utils.enums import AlarmSeverity, SaleStatus


_PRECISION = Decimal("0.001")


class TankReconciliationService:
    """Compare measured stock movement with completed sales and deliveries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def reconcile(
        self,
        *,
        tank_id: int,
        period_start: datetime,
        period_end: datetime,
        opening_level_liters: Decimal,
        actual_closing_level_liters: Decimal,
        raise_alarm: bool = True,
    ) -> TankReconciliationRead:
        tank = self.db.get(Tank, tank_id)
        if tank is None:
            raise NotFoundError("Tank not found.")

        sales = self._sum_completed_sales(tank_id, period_start, period_end)
        deliveries = self._sum_deliveries(tank_id, period_start, period_end)
        expected = (opening_level_liters - sales + deliveries).quantize(_PRECISION)
        difference = (expected - actual_closing_level_liters).quantize(_PRECISION)
        denominator = abs(expected)
        difference_percent = (
            Decimal("0")
            if denominator == 0
            else (abs(difference) * Decimal("100") / denominator).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        reconciled = abs(difference) <= settings.RECONCILIATION_TOLERANCE_LITERS
        result = TankReconciliationRead(
            tank_id=tank_id,
            period_start=period_start,
            period_end=period_end,
            opening_level_liters=opening_level_liters,
            completed_sales_liters=sales,
            delivery_liters=deliveries,
            expected_closing_level_liters=expected,
            actual_closing_level_liters=actual_closing_level_liters,
            difference_liters=difference,
            difference_percent=difference_percent,
            is_reconciled=reconciled,
        )
        if raise_alarm and not reconciled:
            self._raise_mismatch_alarm(tank, period_end, result)
        return result

    def _sum_completed_sales(
        self, tank_id: int, period_start: datetime, period_end: datetime
    ) -> Decimal:
        value = self.db.scalar(
            select(func.coalesce(func.sum(Sale.quantity_liters), 0)).where(
                Sale.tank_id == tank_id,
                Sale.sale_status == SaleStatus.COMPLETED,
                Sale.sale_timestamp >= period_start,
                Sale.sale_timestamp < period_end,
            )
        )
        return Decimal(value or 0).quantize(_PRECISION)

    def _sum_deliveries(
        self, tank_id: int, period_start: datetime, period_end: datetime
    ) -> Decimal:
        value = self.db.scalar(
            select(func.coalesce(func.sum(Delivery.quantity_liters), 0)).where(
                Delivery.tank_id == tank_id,
                Delivery.delivery_timestamp >= period_start,
                Delivery.delivery_timestamp < period_end,
            )
        )
        return Decimal(value or 0).quantize(_PRECISION)

    def _raise_mismatch_alarm(
        self, tank: Tank, moment: datetime, result: TankReconciliationRead
    ) -> None:
        """Use the existing deduplicated alarm engine, never a parallel stream."""

        candidate = RuleAlarmCandidate(
            station_id=tank.station_id,
            target_type="TANK",
            target_id=tank.id,
            alarm_type="TANK_SALES_MISMATCH",
            severity=AlarmSeverity.HIGH,
            moment=moment,
        )
        AlarmEngine(AlarmRepository(self.db)).raise_candidates([candidate])
