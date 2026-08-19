"""Schemas for station fuel price history and pricing previews."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FuelPricePeriod(BaseModel):
    """Shared validation for an effective price interval."""

    effective_from: datetime
    effective_until: datetime | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "FuelPricePeriod":
        if (
            self.effective_until is not None
            and self.effective_until < self.effective_from
        ):
            raise ValueError("effective_until must be later than or equal to effective_from.")
        return self


class FuelPriceCreate(FuelPricePeriod):
    """A new station and fuel-type price-history row."""

    station_id: int = Field(gt=0)
    fuel_type_id: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    is_active: bool = True


class FuelPriceUpdate(BaseModel):
    """Safe, partial update input for a future price row."""

    station_id: int | None = Field(default=None, gt=0)
    fuel_type_id: int | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(
        default=None, gt=0, max_digits=14, decimal_places=4
    )
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    is_active: bool | None = None


class FuelPriceRead(BaseModel):
    """Fuel price history record returned to management clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    station_id: int
    fuel_type_id: int
    unit_price: Decimal
    effective_from: datetime
    effective_until: datetime | None
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class SalePriceCalculationRequest(BaseModel):
    """Read-only price lookup inputs for a prospective sale."""

    customer_id: int = Field(gt=0)
    station_id: int = Field(gt=0)
    fuel_type_id: int = Field(gt=0)
    quantity_liters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    requested_at: datetime | None = None


class SalePriceCalculationResult(BaseModel):
    """Snapshot-ready values to be copied into a future Sale transaction."""

    customer_id: int
    station_id: int
    fuel_type_id: int
    quantity_liters: Decimal
    fuel_price_id: int
    list_unit_price: Decimal
    discount_rate: Decimal
    discount_amount_per_liter: Decimal
    applied_unit_price: Decimal
    total_amount: Decimal
    price_effective_from: datetime
    price_effective_until: datetime | None
    calculated_at: datetime
