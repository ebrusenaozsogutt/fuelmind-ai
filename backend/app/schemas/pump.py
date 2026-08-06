"""Pump API schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.enums import PumpStatus


class PumpBase(BaseModel):
    station_id: int = Field(gt=0)
    tank_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32)
    status: PumpStatus = PumpStatus.IDLE
    nominal_flow_rate: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    minimum_flow_rate: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    maximum_motor_current: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    maximum_pressure: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    last_maintenance_at: datetime | None = None
    total_working_hours: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=14, decimal_places=2
    )
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Pump code cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_flow_rates(self) -> "PumpBase":
        if self.minimum_flow_rate > self.nominal_flow_rate:
            raise ValueError("minimum_flow_rate cannot exceed nominal_flow_rate.")
        return self


class PumpCreate(PumpBase):
    pass


class PumpUpdate(BaseModel):
    station_id: int | None = Field(default=None, gt=0)
    tank_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    status: PumpStatus | None = None
    nominal_flow_rate: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=3
    )
    minimum_flow_rate: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=3
    )
    maximum_motor_current: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=3
    )
    maximum_pressure: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=3
    )
    last_maintenance_at: datetime | None = None
    total_working_hours: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("Pump code cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_supplied_flow_rates(self) -> "PumpUpdate":
        if (
            self.minimum_flow_rate is not None
            and self.nominal_flow_rate is not None
            and self.minimum_flow_rate > self.nominal_flow_rate
        ):
            raise ValueError("minimum_flow_rate cannot exceed nominal_flow_rate.")
        return self


class PumpRead(PumpBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
