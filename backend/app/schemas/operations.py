from datetime import datetime, time
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AttendantBase(BaseModel):
    station_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32)
    full_name: str = Field(min_length=1, max_length=150)
    employee_number: str = Field(min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    is_active: bool = True

    @field_validator("code", "employee_number", "full_name")
    @classmethod
    def clean(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be empty.")
        return value.upper()


class AttendantCreate(AttendantBase):
    pass


class AttendantUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    employee_number: str | None = Field(default=None, min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class AttendantRead(AttendantBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class ShiftBase(BaseModel):
    station_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=32)
    start_time: time
    end_time: time
    is_active: bool = True

    @field_validator("end_time")
    @classmethod
    def valid_time(cls, value: time, info) -> time:
        if value == info.data.get("start_time"):
            raise ValueError("Shift start and end times cannot be equal.")
        return value


class ShiftCreate(ShiftBase):
    pass


class ShiftUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None


class ShiftRead(ShiftBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class AttendantShiftAssignmentCreate(BaseModel):
    attendant_id: int = Field(gt=0)
    shift_id: int = Field(gt=0)
    is_active: bool = True


class AttendantShiftAssignmentRead(AttendantShiftAssignmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    station_id: int
    created_at: datetime
    updated_at: datetime


class AttendantShiftAssignmentUpdate(BaseModel):
    is_active: bool
