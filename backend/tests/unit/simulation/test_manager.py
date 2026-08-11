"""Unit tests for single-process simulation task coordination."""

import asyncio
from types import SimpleNamespace

import pytest

from app.exceptions import BusinessRuleError
from app.models.simulation_run import SimulationRun
from app.simulation.manager import SimulationManager
from app.utils.enums import SimulationMode, SimulationStatus


class FakeSession:
    def close(self) -> None:
        return None


class FakeRunRepository:
    def __init__(self, _: FakeSession, store: SimpleNamespace) -> None:
        self.store = store

    def get(self, run_id: int) -> SimulationRun | None:
        return self.store.runs.get(run_id)

    def list_by_station_and_statuses(
        self, station_id: int, _: set[SimulationStatus]
    ) -> list[SimulationRun]:
        return [
            run
            for run in self.store.runs.values()
            if run.station_id == station_id and run.id != self.store.ignored_run_id
        ]

    def list_by_station_mode_and_statuses(
        self,
        station_id: int,
        _: object,
        __: set[SimulationStatus],
    ) -> list[SimulationRun]:
        return self.list_by_station_and_statuses(station_id, __)


class FakeRunner:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.stopped = asyncio.Event()
        self.paused = False
        self.resume_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.started.set()
        await self.stopped.wait()

    async def pause(self) -> None:
        self.paused = True

    async def resume(self) -> None:
        self.paused = False
        self.resume_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1
        self.stopped.set()

    async def wait_until_started(self) -> None:
        await self.started.wait()


class FakeDatasetGenerator:
    def __init__(self, release: asyncio.Event) -> None:
        self.release = release
        self.started = asyncio.Event()

    async def generate(self) -> None:
        self.started.set()
        await self.release.wait()


@pytest.fixture
def manager_parts(monkeypatch: pytest.MonkeyPatch) -> tuple[SimulationManager, SimpleNamespace]:
    def run(run_id: int, station_id: int, status: SimulationStatus) -> SimulationRun:
        return SimulationRun(
            id=run_id,
            station_id=station_id,
            status=status,
            sequence_number=0,
            generated_sensor_count=0,
            generated_sale_count=0,
            generated_delivery_count=0,
        )

    store = SimpleNamespace(
        runs={1: run(1, 10, SimulationStatus.CREATED), 2: run(2, 20, SimulationStatus.CREATED)},
        ignored_run_id=None,
        created=[],
    )
    monkeypatch.setattr(
        "app.simulation.manager.SimulationRunRepository",
        lambda session: FakeRunRepository(session, store),
    )

    def factory(_: int) -> FakeRunner:
        runner = FakeRunner()
        store.created.append(runner)
        return runner

    return (
        SimulationManager(
            session_factory=FakeSession,
            runner_factory=factory,
            shutdown_timeout_seconds=0.01,
        ),
        store,
    )


@pytest.mark.asyncio
async def test_start_routes_commands_and_stop_cleans_registry(
    manager_parts: tuple[SimulationManager, SimpleNamespace],
) -> None:
    manager, store = manager_parts

    runner = await manager.start_run(1)
    await asyncio.wait_for(runner.started.wait(), timeout=1)
    assert manager.is_active(1)
    await manager.pause_run(1)
    await manager.resume_run(1)
    await manager.stop_run(1)

    assert runner.paused is False
    assert runner.resume_calls == 1
    assert runner.stop_calls == 1
    assert not manager.is_active(1)
    assert manager.get_runner(1) is None
    assert len(store.created) == 1


@pytest.mark.asyncio
async def test_concurrent_start_creates_only_one_task(
    manager_parts: tuple[SimulationManager, SimpleNamespace],
) -> None:
    manager, store = manager_parts

    results = await asyncio.gather(
        manager.start_run(1), manager.start_run(1), return_exceptions=True
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert any(isinstance(result, BusinessRuleError) for result in results)
    assert len(store.created) == 1
    await manager.stop_run(1)


@pytest.mark.asyncio
async def test_station_realtime_conflict_and_different_station(
    manager_parts: tuple[SimulationManager, SimpleNamespace],
) -> None:
    manager, store = manager_parts
    store.runs[3] = SimulationRun(
        id=3,
        station_id=10,
        status=SimulationStatus.CREATED,
        sequence_number=0,
        generated_sensor_count=0,
        generated_sale_count=0,
        generated_delivery_count=0,
    )
    store.runs[4] = SimulationRun(
        id=4,
        station_id=10,
        status=SimulationStatus.RUNNING,
        sequence_number=0,
        generated_sensor_count=0,
        generated_sale_count=0,
        generated_delivery_count=0,
    )
    store.ignored_run_id = 3

    with pytest.raises(BusinessRuleError):
        await manager.start_run(3)

    store.runs.pop(4)
    store.ignored_run_id = 2
    runner = await manager.start_run(2)
    await asyncio.wait_for(runner.started.wait(), timeout=1)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_stops_tasks_and_rejects_new_starts(
    manager_parts: tuple[SimulationManager, SimpleNamespace],
) -> None:
    manager, _ = manager_parts
    runner = await manager.start_run(1)
    await asyncio.wait_for(runner.started.wait(), timeout=1)

    await manager.shutdown()
    await manager.shutdown()

    assert runner.stop_calls == 1
    assert not manager.is_active(1)
    with pytest.raises(BusinessRuleError):
        await manager.start_run(2)


@pytest.mark.asyncio
async def test_dataset_task_is_owned_rejects_duplicate_and_cleans_up(
    manager_parts: tuple[SimulationManager, SimpleNamespace],
) -> None:
    _, store = manager_parts
    store.runs[5] = SimulationRun(
        id=5,
        station_id=30,
        mode=SimulationMode.DATASET,
        status=SimulationStatus.CREATED,
        sequence_number=0,
        generated_sensor_count=0,
        generated_sale_count=0,
        generated_delivery_count=0,
    )
    release = asyncio.Event()
    generated: list[FakeDatasetGenerator] = []

    def dataset_factory(_: int, __: int) -> FakeDatasetGenerator:
        generator = FakeDatasetGenerator(release)
        generated.append(generator)
        return generator

    manager = SimulationManager(
        session_factory=FakeSession,
        runner_factory=lambda _: FakeRunner(),
        dataset_factory=dataset_factory,  # type: ignore[arg-type]
        shutdown_timeout_seconds=0.01,
    )
    await manager.start_dataset_run(5, 30)
    await generated[0].started.wait()
    assert manager.is_dataset_active(5)
    with pytest.raises(BusinessRuleError):
        await manager.start_dataset_run(5, 30)
    release.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert not manager.is_dataset_active(5)


@pytest.mark.asyncio
async def test_normal_start_rejects_dataset_run(
    manager_parts: tuple[SimulationManager, SimpleNamespace],
) -> None:
    manager, store = manager_parts
    store.runs[1].mode = SimulationMode.DATASET
    with pytest.raises(BusinessRuleError, match="DATASET"):
        await manager.start_run(1)
