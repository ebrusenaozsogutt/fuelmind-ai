"""Nozzle API schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import NozzleStatus


class NozzleBase(BaseModel):
    pump_id: int = Field(gt=0)
    fuel_type_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32)
    nozzle_number: int = Field(gt=0)
    status: NozzleStatus = NozzleStatus.AVAILABLE
    totalizer_liters: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=14, decimal_places=3
    )
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Nozzle code cannot be empty.")
        return value


class NozzleCreate(NozzleBase):
    pass


class NozzleUpdate(BaseModel):
    pump_id: int | None = Field(default=None, gt=0)
    fuel_type_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    nozzle_number: int | None = Field(default=None, gt=0)
    status: NozzleStatus | None = None
    totalizer_liters: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("Nozzle code cannot be empty.")
        return value


class NozzleRead(NozzleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pump_code: str
    fuel_type_code: str
    fuel_type_name: str
    created_at: datetime
    updated_at: datetime
