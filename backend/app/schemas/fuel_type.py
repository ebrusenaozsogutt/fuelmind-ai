"""Fuel type API schemas."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FuelTypeBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=32)
    unit: str = Field(default="LITER", min_length=1, max_length=16)
    is_active: bool = True

    @field_validator("code", "unit")
    @classmethod
    def normalize_code_fields(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Code fields cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value


class FuelTypeCreate(FuelTypeBase):
    pass


class FuelTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    unit: str | None = Field(default=None, min_length=1, max_length=16)
    is_active: bool | None = None

    @field_validator("code", "unit")
    @classmethod
    def normalize_optional_code_fields(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("Code fields cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty.")
        return value


class FuelTypeRead(FuelTypeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
