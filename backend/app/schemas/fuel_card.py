"""Fuel-card and card-configuration API schemas."""
# ruff: noqa
from datetime import date, datetime, time
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.utils.enums import CardLimitType, CardStatus, PaymentType

class FuelCardBase(BaseModel):
    vehicle_id: int = Field(gt=0)
    card_code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=150)
    unit_id: str = Field(min_length=1, max_length=100)
    status: CardStatus = CardStatus.ACTIVE
    valid_from: date
    valid_until: date | None = None
    payment_type: PaymentType
    prepaid_balance: Decimal = Field(default=Decimal("0"), ge=0)
    credit_limit: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = True
    @field_validator("card_code", "unit_id")
    @classmethod
    def code(cls, v: str) -> str:
        v = v.strip().upper()
        if not v: raise ValueError("Technical card code cannot be empty.")
        return v
    @field_validator("display_name")
    @classmethod
    def name(cls, v: str) -> str:
        v = v.strip()
        if not v: raise ValueError("Display name cannot be empty.")
        return v
    @model_validator(mode="after")
    def dates(self):
        if self.valid_until is not None and self.valid_until < self.valid_from: raise ValueError("Card validity period is invalid.")
        return self
class FuelCardCreate(FuelCardBase): pass
class FuelCardUpdate(BaseModel):
    vehicle_id: int | None = Field(default=None, gt=0); card_code: str | None = Field(default=None, min_length=1, max_length=64); display_name: str | None = Field(default=None, min_length=1, max_length=150); unit_id: str | None = Field(default=None, min_length=1, max_length=100); status: CardStatus | None = None; valid_from: date | None = None; valid_until: date | None = None; payment_type: PaymentType | None = None; prepaid_balance: Decimal | None = Field(default=None, ge=0); credit_limit: Decimal | None = Field(default=None, ge=0); is_active: bool | None = None
    @field_validator("card_code", "unit_id")
    @classmethod
    def optional_code(cls, v: str | None) -> str | None: return v.strip().upper() if v is not None and v.strip() else None
    @field_validator("display_name")
    @classmethod
    def optional_name(cls, v: str | None) -> str | None: return v.strip() if v is not None and v.strip() else None
class FuelCardRead(FuelCardBase):
    model_config = ConfigDict(from_attributes=True); id: int; credit_used: Decimal; created_at: datetime; updated_at: datetime

class FuelCardLimitBase(BaseModel):
    fuel_card_id: int = Field(gt=0); limit_type: CardLimitType; quantity_limit_liters: Decimal = Field(gt=0); valid_from: date | None = None; valid_until: date | None = None; is_active: bool = True
    @model_validator(mode="after")
    def valid(self):
        if self.valid_until is not None and self.valid_from is not None and self.valid_until < self.valid_from: raise ValueError("Limit validity period is invalid.")
        if self.limit_type == CardLimitType.CUSTOM and (self.valid_from is None or self.valid_until is None): raise ValueError("Custom limits require a date range.")
        return self
class FuelCardLimitCreate(FuelCardLimitBase): pass
class FuelCardLimitUpdate(BaseModel):
    limit_type: CardLimitType | None = None; quantity_limit_liters: Decimal | None = Field(default=None, gt=0); valid_from: date | None = None; valid_until: date | None = None; is_active: bool | None = None
class FuelCardLimitRead(FuelCardLimitBase):
    model_config = ConfigDict(from_attributes=True); id: int; created_at: datetime; updated_at: datetime

class FuelCardAllowedStationCreate(BaseModel): fuel_card_id: int = Field(gt=0); station_id: int = Field(gt=0)
class FuelCardAllowedStationRead(FuelCardAllowedStationCreate): model_config = ConfigDict(from_attributes=True); id: int; created_at: datetime
class FuelCardAllowedFuelTypeCreate(BaseModel): fuel_card_id: int = Field(gt=0); fuel_type_id: int = Field(gt=0)
class FuelCardAllowedFuelTypeRead(FuelCardAllowedFuelTypeCreate): model_config = ConfigDict(from_attributes=True); id: int; created_at: datetime

class FuelCardUsageWindowBase(BaseModel):
    fuel_card_id: int = Field(gt=0); day_of_week: int = Field(ge=0, le=6); start_time: time; end_time: time; is_active: bool = True
    @model_validator(mode="after")
    def times(self):
        if self.start_time >= self.end_time: raise ValueError("Overnight or empty usage windows are not supported.")
        return self
class FuelCardUsageWindowCreate(FuelCardUsageWindowBase): pass
class FuelCardUsageWindowUpdate(BaseModel): day_of_week: int | None = Field(default=None, ge=0, le=6); start_time: time | None = None; end_time: time | None = None; is_active: bool | None = None
class FuelCardUsageWindowRead(FuelCardUsageWindowBase): model_config = ConfigDict(from_attributes=True); id: int; created_at: datetime; updated_at: datetime
