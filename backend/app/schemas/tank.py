"""Tank API schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.enums import SensorStatus


class TankBase(BaseModel):
    station_id: int = Field(gt=0)
    fuel_type_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32)
    capacity_liters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    current_level_liters: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    minimum_safe_level: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    critical_level: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    water_level: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=14, decimal_places=3
    )
    temperature: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    sensor_status: SensorStatus = SensorStatus.ACTIVE
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Tank code cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_levels_within_capacity(self) -> "TankBase":
        for level_name in (
            "current_level_liters",
            "minimum_safe_level",
            "critical_level",
        ):
            if getattr(self, level_name) > self.capacity_liters:
                raise ValueError(f"{level_name} cannot exceed capacity_liters.")
        return self


class TankCreate(TankBase):
    pass


class TankUpdate(BaseModel):
    station_id: int | None = Field(default=None, gt=0)
    fuel_type_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    capacity_liters: Decimal | None = Field(
        default=None, gt=0, max_digits=14, decimal_places=3
    )
    current_level_liters: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    minimum_safe_level: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    critical_level: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    water_level: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    temperature: Decimal | None = Field(default=None, max_digits=6, decimal_places=2)
    sensor_status: SensorStatus | None = None
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("Tank code cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_supplied_levels(self) -> "TankUpdate":
        if self.capacity_liters is None:
            return self
        for level_name in (
            "current_level_liters",
            "minimum_safe_level",
            "critical_level",
        ):
            level = getattr(self, level_name)
            if level is not None and level > self.capacity_liters:
                raise ValueError(f"{level_name} cannot exceed capacity_liters.")
        return self


class TankRead(TankBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
