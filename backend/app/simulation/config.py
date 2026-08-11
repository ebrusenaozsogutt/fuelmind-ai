"""Validated runtime settings for a simulation run."""
#tek bir simülasyon çalıştırması için doğrulanmış çalışma zamanı ayarları.
from pydantic import BaseModel, ConfigDict, Field

from app.utils.simulation_defaults import (
    DEFAULT_PERSIST_EVERY_N_TICKS,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_STEP_SECONDS,
    DEFAULT_SPEED_MULTIPLIER,
    DEFAULT_TICK_INTERVAL_SECONDS,
)


class SimulationConfig(BaseModel):
    """Immutable settings controlling virtual simulation time and persistence."""

    model_config = ConfigDict(frozen=True)

    tick_interval_seconds: float = Field(default=DEFAULT_TICK_INTERVAL_SECONDS, gt=0)
    simulation_step_seconds: int = Field(default=DEFAULT_SIMULATION_STEP_SECONDS, gt=0)
    speed_multiplier: float = Field(default=DEFAULT_SPEED_MULTIPLIER, gt=0)
    random_seed: int = DEFAULT_RANDOM_SEED
    persist_every_n_ticks: int = Field(default=DEFAULT_PERSIST_EVERY_N_TICKS, ge=1)
