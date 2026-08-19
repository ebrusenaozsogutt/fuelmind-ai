"""Composable query parameters shared by persisted-data reports."""

from datetime import date, time

from pydantic import BaseModel, Field, model_validator


class ReportFilters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    time_from: time | None = None
    time_to: time | None = None
    station_id: int | None = Field(default=None, gt=0)
    pump_id: int | None = Field(default=None, gt=0)
    nozzle_id: int | None = Field(default=None, gt=0)
    fuel_type_id: int | None = Field(default=None, gt=0)
    customer_id: int | None = Field(default=None, gt=0)
    vehicle_id: int | None = Field(default=None, gt=0)
    plate: str | None = None
    attendant_id: int | None = Field(default=None, gt=0)
    shift_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "ReportFilters":
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("date_to cannot precede date_from.")
        if self.time_from and self.time_to and self.time_to < self.time_from:
            raise ValueError("time_to cannot precede time_from.")
        return self
