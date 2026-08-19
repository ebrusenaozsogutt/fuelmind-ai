"""Fault API contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.datetime_utils import utc_now
from app.utils.enums import FaultCode, FaultStatus, FaultTargetType, FaultType


class FaultCreate(BaseModel):
    station_id: int = Field(gt=0)
    alarm_id: int | None = Field(default=None, gt=0)
    target_type: FaultTargetType
    target_id: int = Field(gt=0)
    fault_type: FaultType
    fault_code: FaultCode
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    cause: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    detected_at: datetime = Field(default_factory=utc_now)

    @field_validator("started_at", "detected_at")
    @classmethod
    def require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Fault timestamps must include a timezone.")
        return value

    @model_validator(mode="after")
    def timeline_is_valid(self):
        if self.detected_at < self.started_at:
            raise ValueError("detected_at cannot precede started_at.")
        return self


class FaultResolution(BaseModel):
    resolution_note: str = Field(min_length=1)


class FaultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    station_id: int
    alarm_id: int | None
    target_type: FaultTargetType
    target_id: int
    fault_type: FaultType
    fault_code: FaultCode
    title: str
    description: str | None
    cause: str | None
    status: FaultStatus
    started_at: datetime
    detected_at: datetime
    resolved_at: datetime | None
    resolution_note: str | None
    resolved_by: int | None
    created_at: datetime
    updated_at: datetime
