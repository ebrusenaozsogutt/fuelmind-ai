"""Tests for stale simulation run recovery at application startup."""

from datetime import datetime, timezone
import pytest

from app.models.simulation_run import SimulationRun
from app.utils.enums import SimulationStatus
from app.workers.startup_recovery import recover_interrupted_simulation_runs


class FakeSession:
    def __init__(self, *, fail: bool = False) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.fail = fail

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True

    def flush(self) -> None:
        if self.fail:
            raise RuntimeError("write failed")


def _run(run_id: int, status: SimulationStatus) -> SimulationRun:
    return SimulationRun(
        id=run_id,
        station_id=1,
        status=status,
        sequence_number=0,
        generated_sensor_count=0,
        generated_sale_count=0,
        generated_delivery_count=0,
    )


def test_recovery_updates_only_interrupted_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [
        _run(1, SimulationStatus.STARTING),
        _run(2, SimulationStatus.RUNNING),
        _run(3, SimulationStatus.PAUSED),
        _run(4, SimulationStatus.STOPPING),
        _run(5, SimulationStatus.STOPPED),
        _run(6, SimulationStatus.COMPLETED),
        _run(7, SimulationStatus.FAILED),
        _run(8, SimulationStatus.CREATED),
    ]
    session = FakeSession()

    class FakeRepository:
        def __init__(self, _: FakeSession) -> None:
            return None

        def list(self, *, status: SimulationStatus) -> list[SimulationRun]:
            return [run for run in runs if run.status == status]

        def update_status(self, run: SimulationRun, status: SimulationStatus) -> None:
            run.status = status
            session.flush()

        def update_real_ended_at(self, run: SimulationRun, value: datetime) -> None:
            run.real_ended_at = value

        def update_last_error(self, run: SimulationRun, value: str) -> None:
            run.last_error = value

    monkeypatch.setattr(
        "app.workers.startup_recovery.SimulationRunRepository", FakeRepository
    )
    timestamp = datetime(2026, 8, 7, tzinfo=timezone.utc)

    assert recover_interrupted_simulation_runs(
        session_factory=lambda: session,
        recovered_at=timestamp,
    ) == 4
    for run in runs[:4]:
        assert run.status == SimulationStatus.FAILED
        assert run.real_ended_at == timestamp
        assert run.last_error == "Simulation interrupted by backend restart."
    assert [run.status for run in runs[4:]] == [
        SimulationStatus.STOPPED,
        SimulationStatus.COMPLETED,
        SimulationStatus.FAILED,
        SimulationStatus.CREATED,
    ]
    assert session.commits == 1


def test_recovery_rolls_back_and_reraises(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(fail=True)
    run = _run(1, SimulationStatus.RUNNING)

    class FakeRepository:
        def __init__(self, _: FakeSession) -> None:
            return None

        def list(self, *, status: SimulationStatus) -> list[SimulationRun]:
            return [run] if status == SimulationStatus.RUNNING else []

        def update_status(self, _: SimulationRun, __: SimulationStatus) -> None:
            session.flush()

    monkeypatch.setattr(
        "app.workers.startup_recovery.SimulationRunRepository", FakeRepository
    )

    with pytest.raises(RuntimeError, match="write failed"):
        recover_interrupted_simulation_runs(session_factory=lambda: session)
    assert session.commits == 0
    assert session.rollbacks == 1
