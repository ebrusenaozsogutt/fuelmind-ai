"""Async lifecycle runner for one persisted station simulation."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.exceptions import BusinessRuleError, NotFoundError
from app.repositories.simulation_run_repository import SimulationRunRepository
from app.simulation.persistence import TickPersistence
from app.simulation.state import StationSimulationState
from app.simulation.tick_engine import TickEngine
from app.simulation.tick_result import SimulationTickResult
from app.utils.datetime_utils import utc_now
from app.utils.enums import SimulationMode, SimulationStatus

if TYPE_CHECKING:
    from app.live.event_broker import LiveEventBroker

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]
PersistenceFactory = Callable[[Session], TickPersistence]


class SimulationRunner:
    """Manage the async lifecycle of a single simulation run in this process."""

    def __init__(
        self,
        *,
        run_id: int,
        station_state: StationSimulationState,
        tick_engine: TickEngine,
        session_factory: SessionFactory = SessionLocal,
        persistence_factory: PersistenceFactory = TickPersistence,
        mode: SimulationMode = SimulationMode.REALTIME,
        live_event_broker: LiveEventBroker | None = None,
    ) -> None:
        """Create a runner with injected runtime state and short-lived DB sessions."""

        if run_id <= 0:
            raise ValueError("run_id must be positive.")
        if station_state.station_id <= 0:
            raise ValueError("station_state must belong to a station.")
        self.run_id = run_id
        self.station_state = station_state
        self.tick_engine = tick_engine
        self._session_factory = session_factory
        self._persistence_factory = persistence_factory
        self.mode = SimulationMode(mode)
        self._live_event_broker = live_event_broker
        self._tick_buffer: list[SimulationTickResult] = []
        self._stop_requested = asyncio.Event()
        self._resume_requested = asyncio.Event()
        self._resume_requested.set()
        self._status: SimulationStatus | None = None
        self._loop_active = False
        self._has_started = False
        self._started = asyncio.Event()

    @property
    def status(self) -> SimulationStatus | None:
        """Return the runner's last successfully persisted lifecycle status."""

        return self._status

    @property
    def is_running(self) -> bool:
        """Return whether this instance currently owns an active run loop."""

        return self._loop_active

    async def start(self) -> None:
        """Start the run loop and re-raise any simulation or persistence failure."""

        if self._has_started or self._loop_active:
            raise BusinessRuleError("This SimulationRunner instance cannot be started twice.")
        self._has_started = True
        self._loop_active = True
        try:
            await self._begin()
            logger.info("Simulation runner starting: run_id=%s", self.run_id)
            await self._set_status(SimulationStatus.RUNNING)
            self._started.set()
            logger.info("Simulation runner running: run_id=%s", self.run_id)
            while not self._stop_requested.is_set():
                await self._resume_requested.wait()
                if self._stop_requested.is_set():
                    break
                result = self.tick_engine.run_tick(self.station_state)
                self._tick_buffer.append(result)
                if len(self._tick_buffer) >= getattr(
                    self.tick_engine.config, "persist_every_n_ticks", 1
                ):
                    await self._publish_live_results(self._flush_tick_buffer())
                await self._wait_for_next_tick()
            await self._publish_live_results(self._flush_tick_buffer())
            await self._finish_stopped()
        except asyncio.CancelledError:
            logger.info("Simulation runner cancellation requested: run_id=%s", self.run_id)
            await self._handle_cancellation()
            raise
        except (BusinessRuleError, NotFoundError):
            raise
        except Exception as exc:
            logger.exception("Simulation runner failed: run_id=%s", self.run_id)
            await self._mark_failed(exc)
            raise
        finally:
            self._loop_active = False
            self._resume_requested.set()
            self._started.set()

    async def wait_until_started(self) -> None:
        """Wait until startup has persisted RUNNING or terminated with an error."""

        await self._started.wait()

    async def pause(self) -> None:
        """Pause a running simulation before another tick can start."""

        if self._status != SimulationStatus.RUNNING:
            raise BusinessRuleError("Only a RUNNING simulation can be paused.")
        try:
            self._flush_tick_buffer()
        except Exception as exc:
            await self._mark_failed(exc)
            raise
        await self._set_status(SimulationStatus.PAUSED)
        self.tick_engine.clock.pause()
        self._resume_requested.clear()
        logger.info("Simulation runner paused: run_id=%s", self.run_id)

    async def resume(self) -> None:
        """Resume a paused simulation from its unchanged virtual clock state."""

        if self._status != SimulationStatus.PAUSED:
            raise BusinessRuleError("Only a PAUSED simulation can be resumed.")
        await self._set_status(SimulationStatus.RUNNING)
        self.tick_engine.clock.resume()
        self._resume_requested.set()
        logger.info("Simulation runner resumed: run_id=%s", self.run_id)

    async def stop(self) -> None:
        """Request a clean stop without interrupting an in-progress persistence call."""

        if self._status not in {
            SimulationStatus.STARTING,
            SimulationStatus.RUNNING,
            SimulationStatus.PAUSED,
        }:
            raise BusinessRuleError("Only a STARTING, RUNNING, or PAUSED run can stop.")
        await self._set_status(SimulationStatus.STOPPING)
        self._stop_requested.set()
        self._resume_requested.set()
        logger.info("Simulation runner stopping: run_id=%s", self.run_id)

    async def _begin(self) -> None:
        """Validate the stored run and record its first real-world start time."""

        session = self._session_factory()
        try:
            repository = SimulationRunRepository(session)
            run = repository.get(self.run_id)
            if run is None:
                raise NotFoundError(f"Simulation run {self.run_id} was not found.")
            if run.station_id != self.station_state.station_id:
                raise BusinessRuleError("Simulation run does not match the station state.")
            if run.status != SimulationStatus.CREATED:
                raise BusinessRuleError("Only a CREATED simulation run can be started.")
            repository.update_status(run, SimulationStatus.STARTING)
            repository.update_real_started_at(run, utc_now())
            session.commit()
            self._status = SimulationStatus.STARTING
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _persist_tick(self, result: SimulationTickResult) -> None:
        """Persist one result with a newly-created session owned by this tick only."""

        session = self._session_factory()
        try:
            persisted = self._persistence_factory(session).persist(self.run_id, result)
            if not persisted:
                raise RuntimeError("Simulation tick was already persisted or is out of order.")
        finally:
            session.close()

    def _flush_tick_buffer(self) -> list[SimulationTickResult]:
        """Persist buffered ticks in one short-lived transaction without data loss."""

        if not self._tick_buffer:
            return []
        persisted_results = list(self._tick_buffer)
        session = self._session_factory()
        try:
            persistence = self._persistence_factory(session)
            if len(self._tick_buffer) == 1:
                persisted = persistence.persist(self.run_id, self._tick_buffer[0])
            else:
                persisted = persistence.persist_batch(self.run_id, self._tick_buffer)
            if not persisted:
                raise RuntimeError("Simulation tick batch was already persisted or out of order.")
            self._tick_buffer.clear()
        finally:
            session.close()
        return persisted_results

    async def _publish_live_results(self, results: list[SimulationTickResult]) -> None:
        """Publish persisted non-dataset ticks without affecting simulation execution."""

        if self.mode == SimulationMode.DATASET or self._live_event_broker is None:
            return
        for result in results:
            try:
                await self._live_event_broker.publish_simulation_tick(self.run_id, result)
                for alarm in result.created_alarms:
                    await self._live_event_broker.publish_alarm_created(alarm)
            except Exception:
                logger.warning("Live broker escaped publish isolation: run_id=%s sequence=%s", self.run_id, result.sequence_number, exc_info=True)

    async def _set_status(
        self,
        status: SimulationStatus,
        *,
        real_ended: bool = False,
        last_error: str | None = None,
    ) -> None:
        """Commit one lifecycle update through a fresh, short-lived session."""

        session = self._session_factory()
        try:
            repository = SimulationRunRepository(session)
            run = repository.get(self.run_id)
            if run is None:
                raise NotFoundError(f"Simulation run {self.run_id} was not found.")
            repository.update_status(run, status)
            if real_ended:
                repository.update_real_ended_at(run, utc_now())
            if last_error is not None:
                repository.update_last_error(run, last_error)
            session.commit()
            self._status = status
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def _wait_for_next_tick(self) -> None:
        """Sleep asynchronously until the next tick or promptly wake for stop."""

        try:
            await asyncio.wait_for(
                self._stop_requested.wait(),
                timeout=self.tick_engine.config.tick_interval_seconds,
            )
        except TimeoutError:
            return

    async def _finish_stopped(self) -> None:
        """Persist the terminal STOPPED state once the loop has safely exited."""

        if self._status == SimulationStatus.STOPPING:
            await self._set_status(SimulationStatus.STOPPED, real_ended=True)
            logger.info("Simulation runner stopped: run_id=%s", self.run_id)

    async def _mark_failed(self, exc: Exception) -> None:
        """Best-effort terminal failure state that never masks the original error."""

        message = f"Simulation execution failed ({type(exc).__name__})."
        try:
            await self._set_status(
                SimulationStatus.FAILED,
                real_ended=True,
                last_error=message,
            )
            logger.info("Simulation runner failed: run_id=%s", self.run_id)
        except Exception:
            logger.exception("Could not persist FAILED state: run_id=%s", self.run_id)

    async def _handle_cancellation(self) -> None:
        """Best-effort cleanup for cancellation while preserving CancelledError."""

        self._stop_requested.set()
        try:
            self._flush_tick_buffer()
        except Exception:
            logger.exception("Could not flush cancelled run: run_id=%s", self.run_id)
        if self._status in {
            SimulationStatus.STARTING,
            SimulationStatus.RUNNING,
            SimulationStatus.PAUSED,
        }:
            try:
                await self._set_status(SimulationStatus.STOPPING)
                await self._finish_stopped()
            except Exception:
                logger.exception("Could not finalize cancelled run: run_id=%s", self.run_id)
