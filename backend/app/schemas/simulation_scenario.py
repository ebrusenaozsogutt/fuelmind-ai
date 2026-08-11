"""API contracts for simulation scenarios."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import ScenarioType, SimulationStatus, SimulationTargetType


class SimulationScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scenario_type: ScenarioType
    target_type: SimulationTargetType
    target_id: int = Field(gt=0)
    start_time: datetime
    duration_minutes: int = Field(gt=0)
    parameters_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("start_time")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_time must include a timezone.")
        return value


class SimulationScenarioRead(SimulationScenarioCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    simulation_run_id: int
    status: SimulationStatus
    created_at: datetime
