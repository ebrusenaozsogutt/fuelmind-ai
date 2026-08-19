"""Deterministic derivations for optional field-device simulation topology."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.simulation.state import StationSimulationState
from app.utils.enums import ProbeStatus

DEFAULT_TANK_HEIGHT_MM = 2000.0


@dataclass(frozen=True)
class ProbeObservation:
    """A probe-facing view of an already-generated tank measurement."""

    probe_id: int
    tank_id: int
    fuel_height_mm: float
    fuel_volume_liters: float
    water_height_mm: float
    water_volume_liters: float
    temperature_celsius: float
    data_quality_score: float | None = None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def derive_probe_observations(
    station_state: StationSimulationState,
) -> list[ProbeObservation]:
    """Map existing measured tank values to ONLINE active probe observations.

    The station has no calibration table yet. Height values therefore use a
    bounded, deterministic 2000 mm demo conversion from the existing volume
    readings; they do not claim industrial tank-calibration accuracy. Existing
    ``water_level`` is treated as the simulation's volume-like water value and
    is reused directly for ``water_volume_liters`` before the same conversion.
    """

    observations: list[ProbeObservation] = []
    for tank_id in sorted(station_state.active_probes_by_tank):
        probe = station_state.active_probes_by_tank[tank_id]
        if not probe.is_active or probe.status != ProbeStatus.ONLINE:
            continue
        tank = station_state.get_tank(tank_id)
        observations.append(
            ProbeObservation(
                probe_id=probe.probe_id,
                tank_id=tank.tank_id,
                fuel_height_mm=_volume_to_demo_height(
                    tank.measured_level_liters, tank.capacity_liters
                ),
                fuel_volume_liters=tank.measured_level_liters,
                water_height_mm=_volume_to_demo_height(
                    tank.water_level, tank.capacity_liters
                ),
                water_volume_liters=tank.water_level,
                temperature_celsius=tank.temperature,
            )
        )
    return observations


def _volume_to_demo_height(volume_liters: float, capacity_liters: float) -> float:
    """Return a bounded non-calibrated height derived from an existing volume."""

    fill_ratio = min(1.0, max(0.0, volume_liters / capacity_liters))
    return fill_ratio * DEFAULT_TANK_HEIGHT_MM
