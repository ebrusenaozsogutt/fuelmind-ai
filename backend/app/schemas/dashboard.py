"""Read-only operational dashboard summary contract."""

from datetime import datetime

from pydantic import BaseModel


class DashboardSummaryRead(BaseModel):
    station_id: int
    daily_sales_liters: float
    active_alarms: int
    critical_alarms: int
    risky_equipment: int
    station_health_score: int | None
    station_risk_score: float | None
    station_risk_level: str | None
    high_or_critical_risk_count: int
    most_risky_equipment: str | None
    last_ai_assessment_at: datetime | None
