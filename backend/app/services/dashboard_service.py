"""Small, read-only aggregation used by the desktop operational dashboard."""

from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.alarm import Alarm
from app.models.sale import Sale
from app.repositories.station_repository import StationRepository
from app.utils.datetime_utils import utc_now
from app.utils.enums import AlarmSeverity, AlarmStatus


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, station_id: int) -> dict[str, int | float]:
        if StationRepository(self.db).get(station_id) is None:
            raise NotFoundError("Station not found.")
        now = utc_now()
        today_start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        daily_sales = self.db.scalar(
            select(func.coalesce(func.sum(Sale.quantity_liters), 0)).where(
                Sale.station_id == station_id, Sale.sale_timestamp >= today_start
            )
        )
        active_statuses = (AlarmStatus.NEW, AlarmStatus.ACKNOWLEDGED, AlarmStatus.INVESTIGATING)
        active = list(self.db.scalars(select(Alarm).where(Alarm.station_id == station_id, Alarm.status.in_(active_statuses))))
        risky_targets = {
            ("tank", alarm.tank_id) if alarm.tank_id is not None else ("pump", alarm.pump_id)
            for alarm in active if alarm.tank_id is not None or alarm.pump_id is not None
        }
        critical = sum(alarm.severity == AlarmSeverity.CRITICAL for alarm in active)
        health = max(0, 100 - len(active) * 5 - critical * 15 - len(risky_targets) * 2)
        return {"station_id": station_id, "daily_sales_liters": float(daily_sales or 0), "active_alarms": len(active), "critical_alarms": critical, "risky_equipment": len(risky_targets), "station_health_score": health}
