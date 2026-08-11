"""Request and response schemas for simulation run REST operations."""

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.datetime_utils import utc_now
from app.utils.enums import SimulationMode, SimulationStatus
from app.utils.simulation_defaults import (
    DEFAULT_PERSIST_EVERY_N_TICKS,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_STEP_SECONDS,
    DEFAULT_SPEED_MULTIPLIER,
    DEFAULT_TICK_INTERVAL_MS,
)


class SimulationRunCreate(BaseModel):
    """Configuration accepted when an administrator creates a simulation run."""

    station_id: int = Field(gt=0)
    mode: SimulationMode = SimulationMode.REALTIME
    simulation_start_time: datetime = Field(default_factory=utc_now)
    tick_interval_ms: int = Field(default=DEFAULT_TICK_INTERVAL_MS, gt=0)
    simulation_step_seconds: int = Field(default=DEFAULT_SIMULATION_STEP_SECONDS, gt=0)
    speed_multiplier: float = Field(default=DEFAULT_SPEED_MULTIPLIER, gt=0)
    random_seed: int = DEFAULT_RANDOM_SEED
    persist_every_n_ticks: int = Field(default=DEFAULT_PERSIST_EVERY_N_TICKS, gt=0)

    @field_validator("simulation_start_time")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("simulation_start_time must include a timezone.")
        return value


class DatasetGenerationCreate(BaseModel):
    """Configuration for an asynchronously generated historical dataset."""

    station_id: int = Field(gt=0)
    days: int
    simulation_start_time: datetime
    simulation_step_seconds: int = Field(gt=0)
    random_seed: int

    @field_validator("days")
    @classmethod
    def require_supported_days(cls, value: int) -> int:
        if value not in {30, 60, 90}:
            raise ValueError("days must be one of 30, 60, or 90.")
        return value

    @field_validator("simulation_start_time")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("simulation_start_time must include a timezone.")
        return value

    @property
    def target_simulation_time(self) -> datetime:
        return self.simulation_start_time + timedelta(days=self.days)


class SimulationRunRead(BaseModel):
    """Persisted simulation run state exposed through the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    station_id: int
    mode: SimulationMode
    status: SimulationStatus
    simulation_start_time: datetime
    current_simulation_time: datetime | None
    target_simulation_time: datetime | None
    real_started_at: datetime | None
    real_ended_at: datetime | None
    target_simulation_time: datetime | None
    progress_percent: float | None
    tick_interval_ms: int
    simulation_step_seconds: int
    speed_multiplier: float
    random_seed: int
    persist_every_n_ticks: int
    sequence_number: int
    generated_sensor_count: int
    generated_sale_count: int
    generated_delivery_count: int
    last_error: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class SimulationRunStatistics(BaseModel):
    """Lightweight run counters without aggregate data queries."""

    model_config = ConfigDict(from_attributes=True)

    run_id: int
    status: SimulationStatus
    current_simulation_time: datetime | None
    sequence_number: int
    generated_sensor_count: int
    generated_sale_count: int
    generated_delivery_count: int
    real_started_at: datetime | None
    real_ended_at: datetime | None
