"""Delivery API schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.datetime_utils import utc_now


class DeliveryBase(BaseModel):
    tank_id: int = Field(gt=0)
    delivery_timestamp: datetime
    quantity_liters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    level_before: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    level_after: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    supplier_name: str = Field(min_length=1, max_length=150)

    @field_validator("supplier_name")
    @classmethod
    def strip_supplier_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Supplier name cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_level_change(self) -> "DeliveryBase":
        if self.level_after < self.level_before:
            raise ValueError("level_after cannot be less than level_before.")
        return self


class DeliveryCreate(BaseModel):
    """Client-controlled fields for a stock-changing delivery."""

    tank_id: int = Field(gt=0)
    delivery_timestamp: datetime = Field(default_factory=utc_now)
    quantity_liters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    supplier_name: str = Field(min_length=1, max_length=150)

    @field_validator("supplier_name")
    @classmethod
    def strip_supplier_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Supplier name cannot be empty.")
        return value

    @field_validator("delivery_timestamp")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("delivery_timestamp must include a timezone.")
        return value


class DeliveryUpdate(BaseModel):
    tank_id: int | None = Field(default=None, gt=0)
    delivery_timestamp: datetime | None = None
    quantity_liters: Decimal | None = Field(
        default=None, gt=0, max_digits=14, decimal_places=3
    )
    level_before: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    level_after: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=3
    )
    supplier_name: str | None = Field(default=None, min_length=1, max_length=150)

    @field_validator("supplier_name")
    @classmethod
    def strip_optional_supplier_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Supplier name cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_supplied_level_change(self) -> "DeliveryUpdate":
        if (
            self.level_before is not None
            and self.level_after is not None
            and self.level_after < self.level_before
        ):
            raise ValueError("level_after cannot be less than level_before.")
        return self


class DeliveryRead(DeliveryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
