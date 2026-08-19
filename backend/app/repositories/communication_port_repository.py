"""Database queries for communication ports."""

from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.communication_port import CommunicationPort
from app.models.pump import Pump
from app.models.tank_probe import TankProbe


class CommunicationPortRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, port_id: int) -> CommunicationPort | None:
        return self.db.get(CommunicationPort, port_id)

    def list(self) -> list[CommunicationPort]:
        statement = select(CommunicationPort).order_by(
            CommunicationPort.controller_id, CommunicationPort.port_number
        )
        return list(self.db.scalars(statement))

    def get_by_controller_and_number(
        self, controller_id: int, port_number: int
    ) -> CommunicationPort | None:
        return self.db.scalar(
            select(CommunicationPort).where(
                CommunicationPort.controller_id == controller_id,
                CommunicationPort.port_number == port_number,
            )
        )

    def get_by_controller(self, controller_id: int) -> list[CommunicationPort]:
        statement = select(CommunicationPort).where(
            CommunicationPort.controller_id == controller_id
        ).order_by(CommunicationPort.port_number)
        return list(self.db.scalars(statement))

    def create(self, values: dict[str, object]) -> CommunicationPort:
        entity = CommunicationPort(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(
        self, entity: CommunicationPort, values: dict[str, object]
    ) -> CommunicationPort:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: CommunicationPort) -> CommunicationPort:
        entity.is_active = False
        self.db.flush()
        return entity

    def has_attached_devices(self, port_id: int) -> bool:
        return any(
            self.db.scalar(
                select(exists().where(model.communication_port_id == port_id))
            )
            for model in (Pump, TankProbe)
        )
