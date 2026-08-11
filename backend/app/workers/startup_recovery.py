"""Recovery of simulation runs interrupted by a backend restart."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.repositories.simulation_run_repository import SimulationRunRepository
from app.utils.datetime_utils import utc_now
from app.utils.enums import SimulationStatus

_INTERRUPTED_STATUSES = {
    SimulationStatus.STARTING,
    SimulationStatus.RUNNING,
    SimulationStatus.PAUSED,
    SimulationStatus.STOPPING,
}
_RECOVERY_ERROR = "Simulation interrupted by backend restart."

SessionFactory = Callable[[], Session]


def recover_interrupted_simulation_runs(
    *,
    session_factory: SessionFactory = SessionLocal,
    recovered_at: datetime | None = None,
) -> int:
    """Mark all stale active runs FAILED in one short-lived DB transaction."""

    session = session_factory()
    try:
        repository = SimulationRunRepository(session)
        runs = [
            run
            for status in _INTERRUPTED_STATUSES
            for run in repository.list(status=status)
        ]
        timestamp = recovered_at or utc_now()
        for run in runs:
            repository.update_status(run, SimulationStatus.FAILED)
            repository.update_real_ended_at(run, timestamp)
            repository.update_last_error(run, _RECOVERY_ERROR)
        session.commit()
        return len(runs)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
