"""Database queries for simulation runs."""

import builtins
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.simulation_run import SimulationRun
from app.utils.enums import SimulationMode, SimulationStatus


class SimulationRunRepository:
    """Provide persistence primitives without deciding transaction boundaries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, run_id: int) -> SimulationRun | None:
        """Return one run by primary key."""

        return self.db.get(SimulationRun, run_id)

    def get_for_update(self, run_id: int) -> SimulationRun | None:
        """Return one run while holding a row lock for tick persistence."""

        return self.db.scalar(
            select(SimulationRun).where(SimulationRun.id == run_id).with_for_update()
        )

    def list(
        self,
        *,
        station_id: int | None = None,
        status: SimulationStatus | None = None,
        mode: SimulationMode | None = None,
    ) -> list[SimulationRun]:
        """List runs, optionally scoped by station and lifecycle status."""

        statement = select(SimulationRun)
        if station_id is not None:
            statement = statement.where(SimulationRun.station_id == station_id)
        if status is not None:
            statement = statement.where(SimulationRun.status == status)
        if mode is not None:
            statement = statement.where(SimulationRun.mode == mode)
        return list(
            self.db.scalars(statement.order_by(SimulationRun.created_at.desc()))
        )

    def list_by_station_and_statuses(
        self, station_id: int, statuses: set[SimulationStatus]
    ) -> builtins.list[SimulationRun]:
        """List a station's runs in any supplied lifecycle status."""

        if not statuses:
            return []
        return list(
            self.db.scalars(
                select(SimulationRun)
                .where(
                    SimulationRun.station_id == station_id,
                    SimulationRun.status.in_(statuses),
                )
                .order_by(SimulationRun.created_at.desc())
            )
        )

    def list_by_station_mode_and_statuses(
        self,
        station_id: int,
        mode: SimulationMode,
        statuses: set[SimulationStatus],
    ) -> builtins.list[SimulationRun]:
        """List station runs for one persisted mode and lifecycle status set."""

        if not statuses:
            return []
        return list(
            self.db.scalars(
                select(SimulationRun)
                .where(
                    SimulationRun.station_id == station_id,
                    SimulationRun.mode == mode,
                    SimulationRun.status.in_(statuses),
                )
                .order_by(SimulationRun.created_at.desc())
            )
        )

    def create(self, values: dict[str, object]) -> SimulationRun:
        """Add and flush a run without committing it."""

        entity = SimulationRun(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update_status(self, entity: SimulationRun, status: SimulationStatus) -> SimulationRun:
        """Set the lifecycle status and flush the pending update."""

        entity.status = status
        self.db.flush()
        return entity

    def update_current_simulation_time(
        self, entity: SimulationRun, value: datetime
    ) -> SimulationRun:
        """Set the last successfully persisted simulation timestamp."""

        entity.current_simulation_time = value
        self.db.flush()
        return entity

    def update_sequence_number(self, entity: SimulationRun, value: int) -> SimulationRun:
        """Set the last successfully persisted tick sequence."""

        entity.sequence_number = value
        self.db.flush()
        return entity

    def update_generated_sensor_count(self, entity: SimulationRun, value: int) -> SimulationRun:
        """Set the cumulative number of generated sensor records."""

        entity.generated_sensor_count = value
        self.db.flush()
        return entity

    def update_generated_sale_count(self, entity: SimulationRun, value: int) -> SimulationRun:
        """Set the cumulative number of completed generated sales."""

        entity.generated_sale_count = value
        self.db.flush()
        return entity

    def update_generated_delivery_count(
        self, entity: SimulationRun, value: int
    ) -> SimulationRun:
        """Set the cumulative number of generated deliveries."""

        entity.generated_delivery_count = value
        self.db.flush()
        return entity

    def update_real_started_at(self, entity: SimulationRun, value: datetime | None) -> SimulationRun:
        """Set the real-world start timestamp."""

        entity.real_started_at = value
        self.db.flush()
        return entity

    def update_real_ended_at(self, entity: SimulationRun, value: datetime | None) -> SimulationRun:
        """Set the real-world end timestamp."""

        entity.real_ended_at = value
        self.db.flush()
        return entity

    def update_last_error(self, entity: SimulationRun, value: str | None) -> SimulationRun:
        """Set the most recent runner error message."""

        entity.last_error = value
        self.db.flush()
        return entity
