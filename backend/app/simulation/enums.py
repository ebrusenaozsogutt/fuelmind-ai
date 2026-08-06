"""Simulation enum import point without duplicating persisted enum sources."""

from enum import Enum

from app.utils.enums import SimulationStatus, SimulationTargetType


class SimulationMode(str, Enum):
    """Runtime mode used to advance a simulation."""

    REALTIME = "REALTIME"
    ACCELERATED = "ACCELERATED"
    DATASET = "DATASET"


class SourceType(str, Enum):
    """Origin of data consumed by a simulation."""

    SIMULATION = "SIMULATION"
    CSV_IMPORT = "CSV_IMPORT"
    REAL_DEVICE = "REAL_DEVICE"
    MANUAL = "MANUAL"


__all__ = [
    "SimulationMode",
    "SimulationStatus",
    "SimulationTargetType",
    "SourceType",
]
