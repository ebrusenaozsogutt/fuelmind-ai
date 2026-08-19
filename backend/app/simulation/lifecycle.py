"""Shared lifecycle predicates for process-owned realtime simulation runs."""

from app.utils.enums import SimulationMode, SimulationStatus


# These states own station resources only while the in-memory manager still owns
# their runner task. Persisted rows alone can survive a restart and are recovered
# at startup, so they must never be treated as proof of an active simulation.
_RESOURCE_LOCKING_REALTIME_STATUSES = frozenset(
    {
        SimulationStatus.STARTING,
        SimulationStatus.RUNNING,
        SimulationStatus.PAUSED,
        SimulationStatus.STOPPING,
    }
)


def is_station_run_blocking(
    *,
    mode: SimulationMode,
    status: SimulationStatus,
    runner_is_active: bool,
) -> bool:
    """Return whether a manager-owned realtime run currently locks its station."""

    return (
        runner_is_active
        and mode == SimulationMode.REALTIME
        and status in _RESOURCE_LOCKING_REALTIME_STATUSES
    )
