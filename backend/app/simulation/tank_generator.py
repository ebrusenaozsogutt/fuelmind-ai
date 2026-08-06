"""Deterministic in-memory updates for tank sensor state."""

from math import isfinite
from numbers import Real

from app.simulation.random_source import RandomSource
from app.simulation.state import TankState


class TankGenerator:
    """Produce bounded tank sensor measurements using a supplied random source."""

    def __init__(self, *, random_source: RandomSource) -> None:
        """Use the simulation-owned deterministic random source."""

        self._random_source = random_source

    def update_tank(self, *, tank: TankState, elapsed_seconds: float) -> TankState:
        """Update sensor-facing values while preserving the physical fuel level."""

        elapsed_seconds = self._positive_elapsed(elapsed_seconds)
        if not tank.is_active:
            return tank

        level_noise = self._random_source.normal(0.0, 0.15)
        measured_level = min(
            tank.capacity_liters,
            max(0.0, tank.true_level_liters + level_noise),
        )
        temperature_delta = self._random_source.normal(0.0, 0.02) * elapsed_seconds
        water_delta = self._random_source.normal(0.0, 0.001) * elapsed_seconds
        tank.update_measured_level(measured_level)
        tank.temperature += temperature_delta
        tank.water_level = max(0.0, tank.water_level + water_delta)
        return tank

    def update_tanks(
        self, *, tanks: list[TankState], elapsed_seconds: float
    ) -> list[TankState]:
        """Update each supplied tank in stable input order."""

        return [
            self.update_tank(tank=tank, elapsed_seconds=elapsed_seconds) for tank in tanks
        ]

    @staticmethod
    def _positive_elapsed(value: Real) -> float:
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
            raise ValueError("elapsed_seconds must be a finite numeric value.")
        if value <= 0:
            raise ValueError("elapsed_seconds must be greater than zero.")
        return float(value)
