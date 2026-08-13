"""API contracts for anomaly model training and registry management."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.enums import SourceType


class AnomalyModelTrainRequest(BaseModel):
    station_id: int = Field(gt=0)
    model_family: Literal["pump", "tank"]
    start_time: datetime | None = None
    end_time: datetime | None = None
    source_types: list[SourceType] | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def require_aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("training timestamps must include a timezone.")
        return value

    @field_validator("source_types")
    @classmethod
    def reject_empty_sources(
        cls, value: list[SourceType] | None
    ) -> list[SourceType] | None:
        if value == []:
            raise ValueError("source_types cannot be empty when supplied.")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "AnomalyModelTrainRequest":
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time > self.end_time
        ):
            raise ValueError("start_time cannot be after end_time.")
        return self


class ModelVersionRead(BaseModel):
    id: int
    model_type: str
    model_family: str
    version: str
    trained_at: datetime
    training_start_date: date
    training_end_date: date
    training_row_count: int
    feature_count: int | None
    feature_names: list[str]
    is_active: bool
    artifact_available: bool
    artifact_file_name: str
    artifact_size_bytes: int
    artifact_schema_version: int | None
    training_outlier_fraction: float | None
    validation_status: str | None
    scenario_detection_count: int | None
    scenario_total_count: int | None
    normal_false_positive_rate: float | None
    latest_sensor_reading_at: datetime | None
    new_sensor_rows_since_training: int


class AnomalyModelTrainingRead(ModelVersionRead):
    training_diagnostics: dict[str, object]
