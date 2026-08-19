"""Sale API schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import AnomalyType, PaymentType, SaleStatus


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
    customer_id: int | None = None
    fleet_id: int | None = None
    fleet_group_id: int | None = None
    vehicle_id: int | None = None
    driver_id: int | None = None
    fuel_card_id: int | None = None
    nozzle_id: int | None = None
    start_totalizer_liters: Decimal | None = None
    end_totalizer_liters: Decimal | None = None
    list_unit_price: Decimal | None = None
    discount_rate: Decimal | None = None
    sale_status: SaleStatus = SaleStatus.COMPLETED
    authorization_failure_code: str | None = None
    payment_type: PaymentType | None = None
    attendant_id: int | None = Field(default=None, gt=0)
    shift_id: int | None = Field(default=None, gt=0)
    attendant_name: str | None = None
    shift_name: str | None = None


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
    attendant_id: int | None = Field(default=None, gt=0)
    shift_id: int | None = Field(default=None, gt=0)

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


class CommercialSaleRequest(BaseModel):
    """Minimum trusted input for an immediately completed commercial sale."""

    unit_id: str = Field(min_length=1, max_length=100)
    nozzle_id: int = Field(gt=0)
    quantity_liters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    started_at: datetime

    @field_validator("unit_id")
    @classmethod
    def normalize_unit_id(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("unit_id cannot be empty.")
        return value

    @field_validator("started_at")
    @classmethod
    def require_aware_started_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("started_at must include a timezone.")
        return value


class CommercialSaleResponse(BaseModel):
    """Explicit completion or business-rejection outcome for commercial dispensing."""

    completed: bool
    decision_code: str
    message: str
    sale: SaleRead | None = None
