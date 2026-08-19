"""Vehicle API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VehicleBase(BaseModel):
    fleet_group_id: int = Field(gt=0)
    plate: str = Field(min_length=1, max_length=32)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    vehicle_type: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool = True

    @field_validator("plate")
    @classmethod
    def validate_plate(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Vehicle plate cannot be empty.")
        return value


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    fleet_group_id: int | None = Field(default=None, gt=0)
    plate: str | None = Field(default=None, min_length=1, max_length=32)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    vehicle_type: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool | None = None

    @field_validator("plate")
    @classmethod
    def validate_optional_plate(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Vehicle plate cannot be empty.")
        return value


class VehicleRead(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
