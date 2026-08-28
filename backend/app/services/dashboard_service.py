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

    def summary(
        self, station_id: int, *, simulation_run_id: int | None = None
    ) -> dict[str, int | float | str | None]:
        if StationRepository(self.db).get(station_id) is None:
            raise NotFoundError("Station not found.")
        now = utc_now()
        today_start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        sales_statement = select(func.coalesce(func.sum(Sale.quantity_liters), 0)).where(
            Sale.station_id == station_id, Sale.sale_timestamp >= today_start
        )
        if simulation_run_id is not None:
            sales_statement = sales_statement.where(
                Sale.simulation_run_id == simulation_run_id
            )
        daily_sales = self.db.scalar(sales_statement)
        active_statuses = (AlarmStatus.NEW, AlarmStatus.ACKNOWLEDGED, AlarmStatus.INVESTIGATING)
        active = list(self.db.scalars(select(Alarm).where(Alarm.station_id == station_id, Alarm.status.in_(active_statuses))))
        risky_targets = {
            ("tank", alarm.tank_id) if alarm.tank_id is not None else ("pump", alarm.pump_id)
            for alarm in active if alarm.tank_id is not None or alarm.pump_id is not None
        }
        critical = sum(alarm.severity == AlarmSeverity.CRITICAL for alarm in active)
        ai_alarms = [alarm for alarm in active if alarm.anomaly_score is not None]
        # A station is operationally constrained by its riskiest active asset.
        # Using the maximum retains the calibrated 0-100 risk semantics instead
        # of inventing a second scoring scale from alarm counts.
        riskiest = max(ai_alarms, key=lambda alarm: float(alarm.anomaly_score), default=None)
        station_risk = float(riskiest.anomaly_score) if riskiest is not None else None
        high_or_critical = sum(
            (alarm.risk_level or "").upper() in {"HIGH", "CRITICAL"}
            for alarm in ai_alarms
        )
        most_risky_equipment = None
        if riskiest is not None:
            most_risky_equipment = (
                f"Pompa #{riskiest.pump_id}" if riskiest.pump_id is not None
                else f"Tank #{riskiest.tank_id}" if riskiest.tank_id is not None
                else "İstasyon"
            )
        last_ai_assessment_at = max(
            (alarm.detected_at for alarm in ai_alarms), default=None
        )
        return {
            "station_id": station_id,
            "daily_sales_liters": float(daily_sales or 0),
            "active_alarms": len(active),
            "critical_alarms": critical,
            "risky_equipment": len(risky_targets),
            "station_risk_score": station_risk,
            "station_risk_level": riskiest.risk_level if riskiest is not None else None,
            "high_or_critical_risk_count": high_or_critical,
            "most_risky_equipment": most_risky_equipment,
            "last_ai_assessment_at": last_ai_assessment_at,
            # Health is displayed only where an AI risk exists and is explicitly
            # defined as the inverse of that same calibrated risk.
            "station_health_score": None if station_risk is None else round(100 - station_risk),
        }
