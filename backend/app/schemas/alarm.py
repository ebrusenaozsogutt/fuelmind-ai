"""Alarm management API contracts."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict
from app.utils.enums import AlarmSeverity, AlarmStatus


class AlarmRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    station_id: int
    tank_id: int | None
    pump_id: int | None
    alarm_type: str
    severity: AlarmSeverity
    title: str
    description: str | None
    recommended_action: str | None
    probable_causes: list[dict[str, Any]] | None
    status: AlarmStatus
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_note: str | None


class AlarmResolution(BaseModel):
    resolution_note: str | None = None
