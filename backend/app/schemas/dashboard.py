"""Read-only operational dashboard summary contract."""

from pydantic import BaseModel


class DashboardSummaryRead(BaseModel):
    station_id: int
    daily_sales_liters: float
    active_alarms: int
    critical_alarms: int
    risky_equipment: int
    station_health_score: int
