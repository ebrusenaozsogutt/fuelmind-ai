"""Database queries for tank probes."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tank_probe import TankProbe


class TankProbeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, probe_id: int) -> TankProbe | None:
        return self.db.get(TankProbe, probe_id)

    def list(self) -> list[TankProbe]:
        statement = select(TankProbe).order_by(TankProbe.tank_id, TankProbe.code)
        return list(self.db.scalars(statement))

    def get_by_tank(self, tank_id: int) -> list[TankProbe]:
        statement = select(TankProbe).where(TankProbe.tank_id == tank_id).order_by(
            TankProbe.code
        )
        return list(self.db.scalars(statement))

    def get_active_by_tank(self, tank_id: int) -> TankProbe | None:
        return self.db.scalar(
            select(TankProbe).where(
                TankProbe.tank_id == tank_id, TankProbe.is_active.is_(True)
            )
        )

    def create(self, values: dict[str, object]) -> TankProbe:
        entity = TankProbe(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: TankProbe, values: dict[str, object]) -> TankProbe:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: TankProbe) -> TankProbe:
        entity.is_active = False
        self.db.flush()
        return entity
