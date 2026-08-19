"""Driver API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DriverBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    reference_code: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    license_number: str | None = Field(default=None, max_length=64)
    is_active: bool = True

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Driver name cannot be empty.")
        return value

    @field_validator("reference_code", "license_number")
    @classmethod
    def strip_optional_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class DriverCreate(DriverBase):
    pass


class DriverUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    reference_code: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    license_number: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_optional_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Driver name cannot be empty.")
        return value

    @field_validator("reference_code", "license_number")
    @classmethod
    def strip_optional_identifiers(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class DriverRead(DriverBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
