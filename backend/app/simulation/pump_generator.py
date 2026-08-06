"""Deterministic in-memory updates for pump sensor state."""

from math import isfinite
from numbers import Real

from app.simulation.random_source import RandomSource
from app.simulation.state import PumpState


class PumpGenerator:
    """Produce bounded live pump sensor values without changing pump lifecycle state."""

    def __init__(self, *, random_source: RandomSource) -> None:
        """Use the simulation-owned deterministic random source."""

        self._random_source = random_source

    def update_pump(self, *, pump: PumpState, elapsed_seconds: float) -> PumpState:
        """Update an active pump's sensors or reset non-dispensing flow values."""

        elapsed_seconds = self._positive_elapsed(elapsed_seconds)
        if not pump.is_active_status:
            pump.flow_rate = 0.0
            pump.pressure = 0.0
            pump.motor_current = 0.0
            return pump

        flow_rate = self._random_source.clamped_normal(
            pump.nominal_flow_rate,
            max(0.1, pump.nominal_flow_rate * 0.04),
            pump.minimum_flow_rate,
            pump.nominal_flow_rate * 1.15,
        )
        pressure = self._random_source.clamped_normal(
            pump.maximum_pressure * 0.7,
            max(0.05, pump.maximum_pressure * 0.03),
            0.0,
            pump.maximum_pressure,
        )
        motor_current = self._random_source.clamped_normal(
            pump.maximum_motor_current * 0.6,
            max(0.05, pump.maximum_motor_current * 0.03),
            0.0,
            pump.maximum_motor_current,
        )
        temperature = max(
            0.0,
            pump.temperature + self._random_source.normal(0.015, 0.01) * elapsed_seconds,
        )
        pump.set_sensor_values(
            flow_rate=flow_rate,
            pressure=pressure,
            motor_current=motor_current,
            temperature=temperature,
        )
        return pump

    def update_pumps(
        self, *, pumps: list[PumpState], elapsed_seconds: float
    ) -> list[PumpState]:
        """Update each supplied pump in stable input order."""

        return [
            self.update_pump(pump=pump, elapsed_seconds=elapsed_seconds) for pump in pumps
        ]

    @staticmethod
    def _positive_elapsed(value: Real) -> float:
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
            raise ValueError("elapsed_seconds must be a finite numeric value.")
        if value <= 0:
            raise ValueError("elapsed_seconds must be greater than zero.")
        return float(value)
