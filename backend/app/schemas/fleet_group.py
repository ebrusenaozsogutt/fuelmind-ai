"""Fleet-group API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FleetGroupBase(BaseModel):
    fleet_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Fleet group code cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Fleet group name cannot be empty.")
        return value


class FleetGroupCreate(FleetGroupBase):
    pass


class FleetGroupUpdate(BaseModel):
    fleet_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value:
            raise ValueError("Fleet group code cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Fleet group name cannot be empty.")
        return value


class FleetGroupRead(FleetGroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
