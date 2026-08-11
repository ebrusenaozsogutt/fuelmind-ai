"""Single-process coordination for active realtime simulation runners."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.exceptions import BusinessRuleError, NotFoundError
from app.repositories.simulation_run_repository import SimulationRunRepository
from app.simulation.dependencies import build_simulation_runner
from app.simulation.dataset_generator import DatasetGenerator
from app.simulation.runner import SimulationRunner
from app.utils.enums import SimulationMode, SimulationStatus

if TYPE_CHECKING:
    from app.live.event_broker import LiveEventBroker

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {
    SimulationStatus.STARTING,
    SimulationStatus.RUNNING,
    SimulationStatus.PAUSED,
    SimulationStatus.STOPPING,
}
_SHUTDOWN_TIMEOUT_SECONDS = 5.0

SessionFactory = Callable[[], Session]
RunnerFactory = Callable[[int], SimulationRunner]
DatasetFactory = Callable[[int, int], DatasetGenerator]


class SimulationManager:
    """Own runners and tasks for one backend process (single-worker deployment)."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        runner_factory: RunnerFactory | None = None,
        dataset_factory: DatasetFactory | None = None,
        live_event_broker: LiveEventBroker | None = None,
        shutdown_timeout_seconds: float = _SHUTDOWN_TIMEOUT_SECONDS,
    ) -> None:
        """Create an empty, instance-owned runner and task registry."""

        if shutdown_timeout_seconds <= 0:
            raise ValueError("shutdown_timeout_seconds must be positive.")
        self._session_factory = session_factory
        self._runner_factory = runner_factory or (
            lambda run_id: build_simulation_runner(
                run_id,
                session_factory=self._session_factory,
                live_event_broker=live_event_broker,
            )
        )
        self._dataset_factory = dataset_factory or (
            lambda run_id, days: DatasetGenerator(
                runner=self._runner_factory(run_id), days=days, session_factory=self._session_factory
            )
        )
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._runners: dict[int, SimulationRunner] = {}
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._dataset_generators: dict[int, DatasetGenerator] = {}
        self._dataset_tasks: dict[int, asyncio.Task[None]] = {}
        self._run_stations: dict[int, int] = {}
        self._lock = asyncio.Lock()
        self._shutting_down = False

    async def start_run(self, run_id: int) -> SimulationRunner:
        """Create and schedule one realtime run after conflict checks under a lock."""

        async with self._lock:
            if self._shutting_down:
                raise BusinessRuleError("Simulation manager is shutting down.")
            if run_id in self._tasks:
                raise BusinessRuleError(f"Simulation run {run_id} is already active.")
            run = self._get_run(run_id)
            if run.mode == SimulationMode.DATASET:
                raise BusinessRuleError("DATASET runs require the dataset generator workflow.")
            if run.mode == SimulationMode.REALTIME and any(
                active_station_id == run.station_id
                for active_station_id in self._run_stations.values()
            ):
                raise BusinessRuleError(
                    "The station already has an active realtime simulation run."
                )
            if run.mode == SimulationMode.REALTIME:
                self._ensure_station_available(run_id, run.station_id)
            runner = self._runner_factory(run_id)
            task = asyncio.create_task(
                self._run_and_cleanup(run_id, runner),
                name=f"simulation-run-{run_id}",
            )
            self._runners[run_id] = runner
            self._tasks[run_id] = task
            if run.mode == SimulationMode.REALTIME:
                self._run_stations[run_id] = run.station_id
        await runner.wait_until_started()
        # The startup signal is also released when the first tick fails.  Do
        # not acknowledge a failed lifecycle request as a successful start.
        if getattr(runner, "status", None) == SimulationStatus.FAILED:
            failed_run = self._get_run(run_id)
            raise BusinessRuleError(
                failed_run.last_error or "Simulation failed during startup."
            )
        return runner

    async def pause_run(self, run_id: int) -> None:
        """Forward a pause command to an active runner."""

        runner = await self._active_runner(run_id)
        await runner.pause()

    async def start_dataset_run(self, run_id: int, days: int) -> None:
        """Schedule a DATASET generator without retaining an HTTP request."""

        async with self._lock:
            if self._shutting_down:
                raise BusinessRuleError("Simulation manager is shutting down.")
            if run_id in self._dataset_tasks:
                raise BusinessRuleError(f"Dataset run {run_id} is already active.")
            run = self._get_run(run_id)
            if run.mode != SimulationMode.DATASET:
                raise BusinessRuleError("Only DATASET runs use the dataset generator workflow.")
            if run.status != SimulationStatus.CREATED:
                raise BusinessRuleError("Only a CREATED dataset run can be started.")
            generator = self._dataset_factory(run_id, days)
            task = asyncio.create_task(
                self._generate_and_cleanup(run_id, generator), name=f"dataset-run-{run_id}"
            )
            self._dataset_generators[run_id] = generator
            self._dataset_tasks[run_id] = task

    async def resume_run(self, run_id: int) -> None:
        """Forward a resume command to an active runner."""

        runner = await self._active_runner(run_id)
        await runner.resume()

    async def stop_run(self, run_id: int) -> None:
        """Stop a runner and wait until its task has completed and been cleaned up."""

        async with self._lock:
            runner = self._runners.get(run_id)
            task = self._tasks.get(run_id)
        if runner is None or task is None:
            raise NotFoundError(f"Simulation run {run_id} is not active in this process.")
        await runner.stop()
        await task

    def get_runner(self, run_id: int) -> SimulationRunner | None:
        """Return an in-process runner without creating or loading one."""

        return self._runners.get(run_id)

    def is_active(self, run_id: int) -> bool:
        """Return whether this manager currently owns an unfinished task for the run."""

        task = self._tasks.get(run_id)
        return task is not None and not task.done()

    def is_dataset_active(self, run_id: int) -> bool:
        task = self._dataset_tasks.get(run_id)
        return task is not None and not task.done()

    async def wait_for_dataset_run(self, run_id: int) -> None:
        """Wait for a manager-owned dataset task, for CLI and controlled jobs."""

        async with self._lock:
            task = self._dataset_tasks.get(run_id)
        if task is None:
            raise NotFoundError(f"Dataset run {run_id} is not active in this process.")
        await task

    async def shutdown(self) -> None:
        """Stop, await, then cancel remaining runner tasks within a bounded timeout."""

        async with self._lock:
            if self._shutting_down and not self._tasks and not self._dataset_tasks:
                return
            self._shutting_down = True
            runners = list(self._runners.values())
            tasks = list(self._tasks.values())
            dataset_tasks = list(self._dataset_tasks.values())
        for runner in runners:
            try:
                await runner.stop()
            except BusinessRuleError:
                # A task may have completed between the registry snapshot and stop.
                continue
        all_tasks = tasks + dataset_tasks
        if all_tasks:
            done, pending = await asyncio.wait(
                all_tasks,
                timeout=self._shutdown_timeout_seconds,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                try:
                    task.result()
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("Simulation task failed during shutdown")
        async with self._lock:
            self._runners.clear()
            self._tasks.clear()
            self._dataset_generators.clear()
            self._dataset_tasks.clear()
            self._run_stations.clear()

    async def _active_runner(self, run_id: int) -> SimulationRunner:
        """Read one registry entry under the synchronization boundary."""

        async with self._lock:
            runner = self._runners.get(run_id)
            task = self._tasks.get(run_id)
        if runner is None or task is None or task.done():
            raise NotFoundError(f"Simulation run {run_id} is not active in this process.")
        return runner

    async def _run_and_cleanup(self, run_id: int, runner: SimulationRunner) -> None:
        """Own task exceptions and remove completed tasks from the manager registry."""

        try:
            await runner.start()
        except asyncio.CancelledError:
            logger.info("Simulation task cancelled: run_id=%s", run_id)
            raise
        except Exception:
            logger.exception("Simulation task failed: run_id=%s", run_id)
        finally:
            async with self._lock:
                current = asyncio.current_task()
                if self._tasks.get(run_id) is current:
                    self._tasks.pop(run_id, None)
                    self._runners.pop(run_id, None)
                    self._run_stations.pop(run_id, None)

    async def _generate_and_cleanup(self, run_id: int, generator: DatasetGenerator) -> None:
        """Retrieve dataset task outcomes and release its process-owned registry entry."""

        try:
            await generator.generate()
        except asyncio.CancelledError:
            logger.info("Dataset task cancelled: run_id=%s", run_id)
            raise
        except Exception:
            logger.exception("Dataset task failed: run_id=%s", run_id)
        finally:
            async with self._lock:
                current = asyncio.current_task()
                if self._dataset_tasks.get(run_id) is current:
                    self._dataset_tasks.pop(run_id, None)
                    self._dataset_generators.pop(run_id, None)

    def _get_run(self, run_id: int):
        """Load a run through a short-lived session."""

        session = self._session_factory()
        try:
            run = SimulationRunRepository(session).get(run_id)
            if run is None:
                raise NotFoundError(f"Simulation run {run_id} was not found.")
            return run
        finally:
            session.close()

    def _ensure_station_available(self, run_id: int, station_id: int) -> None:
        """Reject a second active realtime run for the same station from DB state."""

        session = self._session_factory()
        try:
            active_runs = SimulationRunRepository(session).list_by_station_mode_and_statuses(
                station_id, SimulationMode.REALTIME, _ACTIVE_STATUSES
            )
        finally:
            session.close()
        if any(active.id != run_id for active in active_runs):
            raise BusinessRuleError(
                "The station already has an active realtime simulation run."
            )
