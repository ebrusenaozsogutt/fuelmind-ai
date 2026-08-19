"""Tank probe API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import ProbeStatus


class TankProbeBase(BaseModel):
    tank_id: int = Field(gt=0)
    communication_port_id: int | None = Field(default=None, gt=0)
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=150)
    device_address: str | None = Field(default=None, max_length=100)
    status: ProbeStatus = ProbeStatus.UNKNOWN
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Probe code cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Probe name cannot be empty.")
        return value


class TankProbeCreate(TankProbeBase):
    pass


class TankProbeUpdate(BaseModel):
    tank_id: int | None = Field(default=None, gt=0)
    communication_port_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    device_address: str | None = Field(default=None, max_length=100)
    status: ProbeStatus | None = None
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("Probe code cannot be empty.")
        return value

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Probe name cannot be empty.")
        return value


class TankProbeRead(TankProbeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_communication_at: datetime | None
    created_at: datetime
    updated_at: datetime
