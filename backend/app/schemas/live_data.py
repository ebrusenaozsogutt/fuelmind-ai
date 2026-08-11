"""Read-only live-history API contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.utils.enums import SourceType


class SensorHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    station_id: int
    tank_id: int | None
    pump_id: int | None
    simulation_run_id: int | None
    sequence_number: int | None
    reading_timestamp: datetime
    tank_level: float | None
    true_tank_level: float | None
    temperature: float | None
    water_level: float | None
    flow_rate: float | None
    pressure: float | None
    motor_current: float | None
    pump_temperature: float | None
    error_count: int
    working_duration: float | None
    data_quality_score: float
    quality_flags_json: list[str]
    source_type: SourceType


class LiveStatusRead(BaseModel):
    station_id: int
    latest_sequence: int | None
    latest_reading_time: datetime | None
    tanks: list[SensorHistoryRead]
    pumps: list[SensorHistoryRead]
