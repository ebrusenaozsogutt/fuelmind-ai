"""Device controller API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import ControllerStatus, ControllerType


class DeviceControllerBase(BaseModel):
    station_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=150)
    controller_type: ControllerType = ControllerType.GENERIC
    status: ControllerStatus = ControllerStatus.OFFLINE
    description: str | None = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Controller code cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Controller name cannot be empty.")
        return value


class DeviceControllerCreate(DeviceControllerBase):
    pass


class DeviceControllerUpdate(BaseModel):
    station_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    controller_type: ControllerType | None = None
    status: ControllerStatus | None = None
    description: str | None = None
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("Controller code cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Controller name cannot be empty.")
        return value


class DeviceControllerRead(DeviceControllerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_communication_at: datetime | None
    created_at: datetime
    updated_at: datetime
