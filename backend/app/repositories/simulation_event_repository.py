"""Database queries for simulation events."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.simulation_event import SimulationEvent


class SimulationEventRepository:
    """Store simulation events without committing caller-owned sessions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, values: dict[str, object]) -> SimulationEvent:
        """Add and flush one event."""

        entity = SimulationEvent(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def create_many(self, values: list[dict[str, object]]) -> list[SimulationEvent]:
        """Add and flush one batch of events in the current transaction."""

        entities = [SimulationEvent(**item) for item in values]
        self.db.add_all(entities)
        self.db.flush()
        return entities

    def list_by_run_id(self, run_id: int) -> list[SimulationEvent]:
        """Return a run's events in their persisted tick order."""

        return list(
            self.db.scalars(
                select(SimulationEvent)
                .where(SimulationEvent.simulation_run_id == run_id)
                .order_by(SimulationEvent.sequence_number, SimulationEvent.id)
            )
        )
