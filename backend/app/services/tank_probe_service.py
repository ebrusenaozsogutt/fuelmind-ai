"""Business rules for tank probes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.tank_probe import TankProbe
from app.repositories.communication_port_repository import CommunicationPortRepository
from app.repositories.tank_probe_repository import TankProbeRepository
from app.repositories.tank_repository import TankRepository
from app.schemas.tank_probe import TankProbeCreate, TankProbeUpdate
from app.utils.enums import PortType


class TankProbeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TankProbeRepository(db)
        self.tank_repository = TankRepository(db)
        self.port_repository = CommunicationPortRepository(db)

    def get(self, probe_id: int) -> TankProbe:
        entity = self.repository.get(probe_id)
        if entity is None:
            raise NotFoundError("Tank probe not found.")
        return entity

    def list(self) -> list[TankProbe]:
        return self.repository.list()

    def list_by_tank(self, tank_id: int) -> list[TankProbe]:
        self._get_tank(tank_id)
        return self.repository.get_by_tank(tank_id)

    def get_active_by_tank(self, tank_id: int) -> TankProbe:
        self._get_tank(tank_id)
        entity = self.repository.get_active_by_tank(tank_id)
        if entity is None:
            raise NotFoundError("Active tank probe not found.")
        return entity

    def create(self, payload: TankProbeCreate) -> TankProbe:
        values = payload.model_dump()
        self._validate_references(
            values["tank_id"], values["communication_port_id"], values["is_active"]
        )
        if values["is_active"]:
            self._validate_active_probe(values["tank_id"])
        return self._commit(lambda: self.repository.create(values))

    def update(self, probe_id: int, payload: TankProbeUpdate) -> TankProbe:
        entity = self.get(probe_id)
        values = payload.model_dump(exclude_unset=True)
        tank_id = values.get("tank_id", entity.tank_id)
        port_id = values.get("communication_port_id", entity.communication_port_id)
        is_active = values.get("is_active", entity.is_active)
        self._validate_references(tank_id, port_id, is_active)
        if is_active:
            self._validate_active_probe(tank_id, exclude_id=entity.id)
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, probe_id: int) -> TankProbe:
        return self._commit(lambda: self.repository.deactivate(self.get(probe_id)))

    def _get_tank(self, tank_id: int):
        tank = self.tank_repository.get(tank_id)
        if tank is None:
            raise NotFoundError("Tank not found.")
        return tank

    def _validate_references(
        self, tank_id: int, communication_port_id: int | None, is_active: bool
    ) -> None:
        tank = self._get_tank(tank_id)
        if communication_port_id is None:
            return
        port = self.port_repository.get(communication_port_id)
        if port is None:
            raise NotFoundError("Port not found.")
        if port.station_id != tank.station_id:
            raise BusinessRuleError(
                "Tank probe and communication port must belong to the same station."
            )
        if port.port_type != PortType.PROBE:
            raise BusinessRuleError("Tank probe can only use a PROBE port.")
        if is_active and not port.is_active:
            raise BusinessRuleError("Active tank probe cannot use an inactive port.")

    def _validate_active_probe(
        self, tank_id: int, *, exclude_id: int | None = None
    ) -> None:
        existing = self.repository.get_active_by_tank(tank_id)
        if existing is not None and existing.id != exclude_id:
            raise BusinessRuleError("Tank already has an active probe.")

    def _commit(self, operation: object) -> TankProbe:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
