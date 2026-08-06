"""Validated runtime settings for a simulation run."""
#tek bir simülasyon çalıştırması için doğrulanmış çalışma zamanı ayarları.
from pydantic import BaseModel, ConfigDict, Field


class SimulationConfig(BaseModel):
    """Immutable settings controlling virtual simulation time and persistence."""

    model_config = ConfigDict(frozen=True)

    tick_interval_seconds: float = Field(default=1.0, gt=0)
    simulation_step_seconds: int = Field(default=5, gt=0)
    speed_multiplier: float = Field(default=1.0, gt=0)
    random_seed: int = 42
    persist_every_n_ticks: int = Field(default=1, ge=1)
