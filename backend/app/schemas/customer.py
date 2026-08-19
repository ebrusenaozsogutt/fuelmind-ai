"""Customer API schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.customer_authorized_person import CustomerAuthorizedPersonRead
from app.schemas.fleet import FleetRead
from app.utils.enums import CustomerRequestStatus, CustomerType


class CustomerBase(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=150)
    customer_type: CustomerType
    sector: str | None = Field(default=None, max_length=100)
    tax_number: str | None = Field(default=None, max_length=32)
    tax_office: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    address: str | None = None
    registration_date: date | None = None
    discount_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    request_status: CustomerRequestStatus = CustomerRequestStatus.PENDING
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Customer code cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Customer name cannot be empty.")
        return value


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    customer_type: CustomerType | None = None
    sector: str | None = Field(default=None, max_length=100)
    tax_number: str | None = Field(default=None, max_length=32)
    tax_office: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    address: str | None = None
    registration_date: date | None = None
    discount_rate: Decimal | None = Field(default=None, ge=0, le=100)
    request_status: CustomerRequestStatus | None = None
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value:
            raise ValueError("Customer code cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Customer name cannot be empty.")
        return value


class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    registration_date: date
    created_at: datetime
    updated_at: datetime


class CustomerDetailRead(BaseModel):
    customer: CustomerRead
    authorized_persons: list[CustomerAuthorizedPersonRead]
    fleets: list[FleetRead]
