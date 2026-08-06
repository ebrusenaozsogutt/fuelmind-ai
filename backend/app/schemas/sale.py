"""Sale API schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import AnomalyType


class SaleBase(BaseModel):
    station_id: int = Field(gt=0)
    tank_id: int = Field(gt=0)
    pump_id: int = Field(gt=0)
    fuel_type_id: int = Field(gt=0)
    sale_timestamp: datetime
    quantity_liters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    total_amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    duration_seconds: int = Field(ge=0)
    level_before: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    level_after: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    is_anomaly: bool = False
    anomaly_score: Decimal | None = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    anomaly_type: AnomalyType | None = None


class SaleCreate(BaseModel):
    """Client-controlled fields for a stock-changing sale."""

    station_id: int = Field(gt=0)
    tank_id: int = Field(gt=0)
    pump_id: int = Field(gt=0)
    fuel_type_id: int = Field(gt=0)
    sale_timestamp: datetime
    quantity_liters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    duration_seconds: int = Field(ge=0)
    is_anomaly: bool = False
    anomaly_score: Decimal | None = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    anomaly_type: AnomalyType | None = None

    @field_validator("sale_timestamp")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sale_timestamp must include a timezone.")
        return value


class SaleUpdate(BaseModel):
    station_id: int | None = Field(default=None, gt=0)
    tank_id: int | None = Field(default=None, gt=0)
    pump_id: int | None = Field(default=None, gt=0)
    fuel_type_id: int | None = Field(default=None, gt=0)
    sale_timestamp: datetime | None = None
    quantity_liters: Decimal | None = Field(
        default=None, gt=0, max_digits=14, decimal_places=3
    )
    unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=4
    )
    total_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=16, decimal_places=2
    )
    duration_seconds: int | None = Field(default=None, ge=0)
    level_before: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    level_after: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    is_anomaly: bool | None = None
    anomaly_score: Decimal | None = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    anomaly_type: AnomalyType | None = None


class SaleRead(SaleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
