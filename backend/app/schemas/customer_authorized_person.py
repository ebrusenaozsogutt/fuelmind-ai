"""Customer authorized-person API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerAuthorizedPersonBase(BaseModel):
    customer_id: int = Field(gt=0)
    full_name: str = Field(min_length=1, max_length=150)
    title: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    is_primary: bool = False
    is_active: bool = True

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Authorized person name cannot be empty.")
        return value


class CustomerAuthorizedPersonCreate(CustomerAuthorizedPersonBase):
    pass


class CustomerAuthorizedPersonUpdate(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    title: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    is_primary: bool | None = None
    is_active: bool | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_optional_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Authorized person name cannot be empty.")
        return value


class CustomerAuthorizedPersonRead(CustomerAuthorizedPersonBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
