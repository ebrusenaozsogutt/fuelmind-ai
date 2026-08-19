"""Best-effort coordination of live simulation tick publishing."""

from __future__ import annotations

import logging

from app.live.connection_manager import ConnectionManager
from app.live.serializers import serialize_alarm_created, serialize_anomaly_evaluation, serialize_simulation_tick
from app.services.live_topology_service import LiveTopologySnapshot
from app.simulation.tick_result import SimulationTickResult

logger = logging.getLogger(__name__)


class LiveEventBroker:
    """Publish serialized simulation ticks through the shared connection manager."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._connection_manager = connection_manager
        self._last_sequences: dict[int, int] = {}

    async def publish_simulation_tick(
        self,
        simulation_run_id: int,
        tick_result: SimulationTickResult,
        *,
        topology: LiveTopologySnapshot | None = None,
    ) -> None:
        """Best-effort publish that never propagates live transport failures."""

        try:
            previous = self._last_sequences.get(simulation_run_id)
            sequence = tick_result.sequence_number
            if previous is not None:
                if sequence == previous:
                    logger.warning("Live duplicate sequence dropped: run_id=%s sequence=%s", simulation_run_id, sequence)
                    return
                if sequence < previous:
                    logger.warning("Live out-of-order sequence dropped: run_id=%s sequence=%s", simulation_run_id, sequence)
                    return
                if sequence > previous + 1:
                    logger.warning("Live sequence gap detected: run_id=%s expected=%s received=%s", simulation_run_id, previous + 1, sequence)
            self._last_sequences[simulation_run_id] = sequence
            if len(self._last_sequences) > 1000:
                self._last_sequences.pop(next(iter(self._last_sequences)))
            await self._connection_manager.broadcast(
                tick_result.station_id,
                serialize_simulation_tick(
                    simulation_run_id, tick_result, topology=topology
                ),
            )
        except Exception:
            logger.warning("Failed to publish live simulation tick: run_id=%s station_id=%s sequence=%s", simulation_run_id, tick_result.station_id, tick_result.sequence_number, exc_info=True)

    async def publish_alarm_created(self, alarm: object) -> None:
        """Publish only alarms which have already been committed by persistence."""
        try:
            await self._connection_manager.broadcast(alarm.station_id, serialize_alarm_created(alarm))
        except Exception:
            logger.warning("Failed to publish alarm: alarm_id=%s", getattr(alarm, "id", None), exc_info=True)

    async def publish_anomaly_evaluation(self, simulation_run_id: int, tick_result: SimulationTickResult) -> None:
        if not tick_result.ai_results:
            return
        try:
            await self._connection_manager.broadcast(
                tick_result.station_id,
                serialize_anomaly_evaluation(simulation_run_id, tick_result),
            )
        except Exception:
            logger.warning(
                "Failed to publish live anomaly evaluation: run_id=%s sequence=%s",
                simulation_run_id, tick_result.sequence_number, exc_info=True,
            )
