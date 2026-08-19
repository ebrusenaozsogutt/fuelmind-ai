"""Database queries for nozzles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nozzle import Nozzle


class NozzleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, nozzle_id: int) -> Nozzle | None:
        return self.db.get(Nozzle, nozzle_id)

    def get_for_update(self, nozzle_id: int) -> Nozzle | None:
        return self.db.scalar(select(Nozzle).where(Nozzle.id == nozzle_id).with_for_update())

    def list(self) -> list[Nozzle]:
        statement = select(Nozzle).order_by(Nozzle.pump_id, Nozzle.nozzle_number)
        return list(self.db.scalars(statement))

    def get_by_pump(self, pump_id: int) -> list[Nozzle]:
        statement = select(Nozzle).where(Nozzle.pump_id == pump_id).order_by(
            Nozzle.nozzle_number
        )
        return list(self.db.scalars(statement))

    def get_by_pump_and_number(
        self, pump_id: int, nozzle_number: int
    ) -> Nozzle | None:
        return self.db.scalar(
            select(Nozzle).where(
                Nozzle.pump_id == pump_id,
                Nozzle.nozzle_number == nozzle_number,
            )
        )

    def create(self, values: dict[str, object]) -> Nozzle:
        entity = Nozzle(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Nozzle, values: dict[str, object]) -> Nozzle:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: Nozzle) -> Nozzle:
        entity.is_active = False
        self.db.flush()
        return entity
