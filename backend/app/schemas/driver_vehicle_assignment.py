"""Driver vehicle assignment API schemas."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.utils.enums import DriverAssignmentStatus


class DriverVehicleAssignmentBase(BaseModel):
    driver_id: int = Field(gt=0)
    vehicle_id: int = Field(gt=0)
    assigned_from: date
    assigned_until: date | None = None
    status: DriverAssignmentStatus = DriverAssignmentStatus.ACTIVE

    @model_validator(mode="after")
    def validate_date_range(self) -> "DriverVehicleAssignmentBase":
        if self.assigned_until is not None and self.assigned_until < self.assigned_from:
            raise ValueError("Assignment end date cannot precede start date.")
        return self


class DriverVehicleAssignmentCreate(DriverVehicleAssignmentBase):
    pass


class DriverVehicleAssignmentUpdate(BaseModel):
    driver_id: int | None = Field(default=None, gt=0)
    vehicle_id: int | None = Field(default=None, gt=0)
    assigned_from: date | None = None
    assigned_until: date | None = None
    status: DriverAssignmentStatus | None = None


class DriverVehicleAssignmentRead(DriverVehicleAssignmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
