"""Communication port API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import PortStatus, PortType


class CommunicationPortBase(BaseModel):
    controller_id: int = Field(gt=0)
    port_number: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=150)
    port_type: PortType = PortType.GENERIC
    protocol: str | None = Field(default=None, max_length=100)
    baud_rate: int | None = Field(default=None, gt=0)
    status: PortStatus = PortStatus.OFFLINE
    device_path: str | None = Field(default=None, max_length=255)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Port name cannot be empty.")
        return value

    @field_validator("protocol", "device_path")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CommunicationPortCreate(CommunicationPortBase):
    pass


class CommunicationPortUpdate(BaseModel):
    controller_id: int | None = Field(default=None, gt=0)
    port_number: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    port_type: PortType | None = None
    protocol: str | None = Field(default=None, max_length=100)
    baud_rate: int | None = Field(default=None, gt=0)
    status: PortStatus | None = None
    device_path: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Port name cannot be empty.")
        return value

    @field_validator("protocol", "device_path")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CommunicationPortRead(CommunicationPortBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    controller_code: str
    station_id: int
    last_communication_at: datetime | None
    created_at: datetime
    updated_at: datetime
