"""Contracts for importing raw (not engineered) training sensor readings."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ManualSensorReading(BaseModel):
    timestamp: datetime
    tank_id: int | None = Field(default=None, gt=0)
    pump_id: int | None = Field(default=None, gt=0)
    tank_level: Decimal | None = Field(default=None, ge=0)
    true_tank_level: Decimal | None = Field(default=None, ge=0)
    temperature: Decimal | None = None
    water_level: Decimal | None = Field(default=None, ge=0)
    flow_rate: Decimal | None = Field(default=None, ge=0)
    pressure: Decimal | None = Field(default=None, ge=0)
    motor_current: Decimal | None = Field(default=None, ge=0)
    pump_temperature: Decimal | None = None
    error_count: int = Field(default=0, ge=0)
    working_duration: Decimal | None = Field(default=None, ge=0)
    data_quality_score: Decimal = Field(default=Decimal("100"), ge=0, le=100)

    @field_validator("timestamp")
    @classmethod
    def timestamp_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Zaman damgası saat dilgisi içermelidir.")
        return value

    @model_validator(mode="after")
    def require_target_and_family_signals(self) -> "ManualSensorReading":
        if self.tank_id is None and self.pump_id is None:
            raise ValueError("Tank veya pompa seçilmelidir.")
        if self.pump_id is not None and not all(
            value is not None for value in (self.flow_rate, self.pressure, self.motor_current)
        ):
            raise ValueError("Pompa verisi için debi, basınç ve motor akımı zorunludur.")
        if self.pump_id is None and not all(
            value is not None for value in (self.tank_level, self.true_tank_level, self.temperature, self.water_level)
        ):
            raise ValueError("Tank verisi için seviye, gerçek seviye, sıcaklık ve su seviyesi zorunludur.")
        return self


class ManualSensorIngestRequest(BaseModel):
    station_id: int = Field(gt=0)
    rows: list[ManualSensorReading] = Field(min_length=1, max_length=10_000)


class SensorImportResult(BaseModel):
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    errors: list[str] = []


ModelFamily = Literal["pump", "tank"]

