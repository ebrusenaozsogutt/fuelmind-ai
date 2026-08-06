"""Station API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StationBase(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=150)
    city: str = Field(min_length=1, max_length=100)
    district: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Station code cannot be empty.")
        return value

    @field_validator("name", "city", "district", "address")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class StationCreate(StationBase):
    pass


class StationUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    district: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("Station code cannot be empty.")
        return value

    @field_validator("name", "city", "district", "address")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class StationRead(StationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
