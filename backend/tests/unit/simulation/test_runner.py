"""Deterministic lifecycle tests for SimulationRunner."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.exceptions import BusinessRuleError
from app.models.simulation_run import SimulationRun
from app.simulation.runner import SimulationRunner
from app.utils.enums import SimulationMode, SimulationStatus


class FakeSession:
    """Short-lived session fake that exposes committed run states."""

    def __init__(self, store: SimpleNamespace) -> None:
        self.store = store
        self.closed = False

    def get(self, _: type[SimulationRun], __: int) -> SimulationRun:
        return self.store.run

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.store.committed_statuses.append(self.store.run.status)

    def rollback(self) -> None:
        self.store.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakeClock:
    """Expose the clock controls used by the runner without advancing time itself."""

    def __init__(self) -> None:
        self.is_paused = False
        self.current_time = datetime(2026, 8, 7, tzinfo=timezone.utc)

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False


class FakeTickEngine:
    """Produce observable ticks and optionally fail at a controlled point."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.config = SimpleNamespace(tick_interval_seconds=0.001)
        self.clock = FakeClock()
        self.error = error
        self.calls = 0
        self.tick_created = asyncio.Event()

    def run_tick(self, _: object) -> SimpleNamespace:
        self.calls += 1
        self.tick_created.set()
        if self.error is not None:
            raise self.error
        self.clock.current_time = datetime(2026, 8, 7, 0, 0, self.calls, tzinfo=timezone.utc)
        return SimpleNamespace(sequence_number=self.calls)


class FakePersistence:
    """Capture tick persistence calls and optionally fail."""

    def __init__(self, _: FakeSession, store: SimpleNamespace) -> None:
        self.store = store

    def persist(self, run_id: int, result: SimpleNamespace) -> bool:
        self.store.persisted.append((run_id, result.sequence_number))
        if self.store.persistence_error is not None:
            raise self.store.persistence_error
        return True


class FakeLiveBroker:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.calls: list[tuple[int, int]] = []

    async def publish_simulation_tick(self, run_id: int, result: SimpleNamespace) -> None:
        if self.fails:
            raise RuntimeError("live transport failure")
        self.calls.append((run_id, result.sequence_number))


@pytest.fixture
def runner_parts() -> tuple[SimulationRunner, SimpleNamespace, FakeTickEngine]:
    """Create a runner with fully isolated session and persistence fakes."""

    run = SimulationRun(
        id=5,
        station_id=9,
        status=SimulationStatus.CREATED,
        sequence_number=0,
        generated_sensor_count=0,
        generated_sale_count=0,
        generated_delivery_count=0,
    )
    store = SimpleNamespace(
        run=run,
        sessions=[],
        persisted=[],
        committed_statuses=[],
        rollbacks=0,
        persistence_error=None,
    )

    def session_factory() -> FakeSession:
        session = FakeSession(store)
        store.sessions.append(session)
        return session

    engine = FakeTickEngine()
    runner = SimulationRunner(
        run_id=5,
        station_state=SimpleNamespace(station_id=9),
        tick_engine=engine,
        session_factory=session_factory,
        persistence_factory=lambda session: FakePersistence(session, store),
    )
    return runner, store, engine


async def _start_until_first_tick(
    runner: SimulationRunner, engine: FakeTickEngine
) -> asyncio.Task[None]:
    task = asyncio.create_task(runner.start())
    await asyncio.wait_for(engine.tick_created.wait(), timeout=1)
    return task


@pytest.mark.asyncio
async def test_start_runs_tick_and_uses_short_lived_sessions(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    """CREATED progresses through STARTING and RUNNING before persisting a tick."""

    runner, store, engine = runner_parts
    task = await _start_until_first_tick(runner, engine)

    assert store.committed_statuses[:2] == [
        SimulationStatus.STARTING,
        SimulationStatus.RUNNING,
    ]
    assert store.run.real_started_at is not None
    assert store.persisted == [(5, 1)]
    assert len(store.sessions) >= 3
    assert all(session.closed for session in store.sessions)

    await runner.stop()
    await task
    assert store.run.status == SimulationStatus.STOPPED
    assert store.run.real_ended_at is not None


@pytest.mark.asyncio
async def test_pause_preserves_virtual_time_and_resume_continues(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    """A paused loop creates no ticks until resume releases its event wait."""

    runner, store, engine = runner_parts
    task = await _start_until_first_tick(runner, engine)
    await runner.pause()
    paused_calls = engine.calls
    paused_time = engine.clock.current_time
    await asyncio.sleep(0.01)

    assert engine.calls == paused_calls
    assert engine.clock.current_time == paused_time
    assert store.run.status == SimulationStatus.PAUSED

    await runner.resume()
    for _ in range(20):
        if engine.calls > paused_calls:
            break
        await asyncio.sleep(0.001)
    assert engine.calls > paused_calls
    await runner.stop()
    await task


@pytest.mark.asyncio
async def test_stop_from_paused_releases_wait_without_another_tick(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    """Stopping a paused runner reaches STOPPED without advancing the engine."""

    runner, store, engine = runner_parts
    task = await _start_until_first_tick(runner, engine)
    await runner.pause()
    calls = engine.calls
    await runner.stop()
    await task

    assert engine.calls == calls
    assert store.run.status == SimulationStatus.STOPPED
    assert store.run.real_ended_at is not None


@pytest.mark.asyncio
async def test_tick_engine_failure_marks_run_failed(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    """Unexpected tick exceptions stop the loop and retain a safe error description."""

    runner, store, engine = runner_parts
    engine.error = ValueError("diagnostic that must not be stored")

    with pytest.raises(ValueError):
        await runner.start()

    assert store.run.status == SimulationStatus.FAILED
    assert store.run.real_ended_at is not None
    assert store.run.last_error == "Simulation execution failed (ValueError)."
    assert engine.calls == 1


@pytest.mark.asyncio
async def test_persistence_failure_marks_run_failed(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    """Persistence errors propagate and prevent the next tick from starting."""

    runner, store, engine = runner_parts
    store.persistence_error = RuntimeError("postgresql://secret")

    with pytest.raises(RuntimeError):
        await runner.start()

    assert store.run.status == SimulationStatus.FAILED
    assert store.run.last_error == "Simulation execution failed (RuntimeError)."
    assert engine.calls == 1


@pytest.mark.asyncio
async def test_invalid_commands_and_second_start_are_rejected(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    """Invalid lifecycle commands never pretend to be successful."""

    runner, _, engine = runner_parts
    with pytest.raises(BusinessRuleError):
        await runner.pause()
    with pytest.raises(BusinessRuleError):
        await runner.resume()

    task = await _start_until_first_tick(runner, engine)
    with pytest.raises(BusinessRuleError):
        await runner.start()
    await runner.stop()
    await task
    with pytest.raises(BusinessRuleError):
        await runner.start()


@pytest.mark.asyncio
async def test_cancellation_finalizes_run_and_reraises_cancelled_error(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    """Cancellation is not converted into a normal failure result."""

    runner, store, engine = runner_parts
    task = await _start_until_first_tick(runner, engine)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert store.run.status == SimulationStatus.STOPPED
    assert store.run.real_ended_at is not None


@pytest.mark.asyncio
async def test_realtime_publishes_persisted_tick(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    runner, store, engine = runner_parts
    broker = FakeLiveBroker()
    runner._live_event_broker = broker  # type: ignore[assignment]
    task = await _start_until_first_tick(runner, engine)
    assert broker.calls == [(5, 1)]
    await runner.stop()
    await task


@pytest.mark.asyncio
async def test_live_publish_failure_does_not_fail_run(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    runner, store, engine = runner_parts
    runner._live_event_broker = FakeLiveBroker(fails=True)  # type: ignore[assignment]
    task = await _start_until_first_tick(runner, engine)
    assert store.run.status == SimulationStatus.RUNNING
    await runner.stop()
    await task
    assert store.run.status == SimulationStatus.STOPPED


@pytest.mark.asyncio
async def test_dataset_runner_does_not_publish_live_ticks(
    runner_parts: tuple[SimulationRunner, SimpleNamespace, FakeTickEngine],
) -> None:
    runner, _, engine = runner_parts
    broker = FakeLiveBroker()
    runner.mode = SimulationMode.DATASET
    runner._live_event_broker = broker  # type: ignore[assignment]
    task = await _start_until_first_tick(runner, engine)
    assert broker.calls == []
    await runner.stop()
    await task
