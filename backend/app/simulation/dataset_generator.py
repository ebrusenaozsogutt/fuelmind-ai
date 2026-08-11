"""Bounded-memory historical dataset execution using existing tick persistence."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.repositories.simulation_run_repository import SimulationRunRepository
from app.simulation.persistence import TickPersistence
from app.simulation.runner import SimulationRunner
from app.utils.datetime_utils import utc_now
from app.utils.enums import SimulationStatus

DEFAULT_DATASET_TICK_BATCH_SIZE = 100


class DatasetGenerator:
    """Generate 30/60/90-day histories without realtime sleeps."""

    def __init__(
        self,
        *,
        runner: SimulationRunner,
        days: int,
        session_factory: Callable[[], Session] = SessionLocal,
        tick_batch_size: int = DEFAULT_DATASET_TICK_BATCH_SIZE,
    ) -> None:
        if days not in {30, 60, 90}:
            raise ValueError("days must be one of 30, 60, or 90.")
        if tick_batch_size <= 0:
            raise ValueError("tick_batch_size must be positive.")
        self.runner = runner
        self.days = days
        self._session_factory = session_factory
        self._tick_batch_size = tick_batch_size

    async def generate(self) -> None:
        """Generate and persist all ticks, ending only after a final batch commit."""
        await self._set_status(SimulationStatus.STARTING, started=True)
        try:
            await self._set_status(SimulationStatus.RUNNING)
            target = self.runner.tick_engine.clock.current_time + timedelta(days=self.days)
            buffer = []
            while self.runner.tick_engine.clock.current_time < target:
                result = self.runner.tick_engine.run_tick(self.runner.station_state)
                if result.simulation_time > target:
                    break
                buffer.append(result)
                if len(buffer) >= self._tick_batch_size:
                    self._persist(buffer)
                    buffer.clear()
                    await asyncio.sleep(0)
            if buffer:
                self._persist(buffer)
            await self._set_status(SimulationStatus.COMPLETED, ended=True, clear_error=True)
        except asyncio.CancelledError:
            await self._set_status(SimulationStatus.FAILED, ended=True, error="Dataset generation cancelled.")
            raise
        except Exception as exc:
            await self._set_status(
                SimulationStatus.FAILED,
                ended=True,
                error=f"Dataset generation failed ({type(exc).__name__}).",
            )
            raise

    def _persist(self, results: list[object]) -> None:
        session = self._session_factory()
        try:
            TickPersistence(session).persist_batch(self.runner.run_id, results)  # type: ignore[arg-type]
        finally:
            session.close()

    async def _set_status(self, status: SimulationStatus, *, started: bool = False, ended: bool = False, error: str | None = None, clear_error: bool = False) -> None:
        session = self._session_factory()
        try:
            repo = SimulationRunRepository(session)
            run = repo.get(self.runner.run_id)
            if run is None:
                raise ValueError("Simulation run was not found.")
            repo.update_status(run, status)
            if started:
                repo.update_real_started_at(run, utc_now())
            if ended:
                repo.update_real_ended_at(run, utc_now())
            if error is not None or clear_error:
                repo.update_last_error(run, error)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
