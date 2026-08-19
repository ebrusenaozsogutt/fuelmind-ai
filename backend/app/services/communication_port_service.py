"""Business rules for device-controller communication ports."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.communication_port import CommunicationPort
from app.repositories.communication_port_repository import CommunicationPortRepository
from app.repositories.device_controller_repository import DeviceControllerRepository
from app.schemas.communication_port import CommunicationPortCreate, CommunicationPortUpdate
from app.utils.enums import PortType


class CommunicationPortService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CommunicationPortRepository(db)
        self.controller_repository = DeviceControllerRepository(db)

    def get(self, port_id: int) -> CommunicationPort:
        entity = self.repository.get(port_id)
        if entity is None:
            raise NotFoundError("Port not found.")
        return entity

    def list(self) -> list[CommunicationPort]:
        return self.repository.list()

    def list_by_controller(self, controller_id: int) -> list[CommunicationPort]:
        self._validate_controller(controller_id)
        return self.repository.get_by_controller(controller_id)

    def create(self, payload: CommunicationPortCreate) -> CommunicationPort:
        values = payload.model_dump()
        self._validate_controller(values["controller_id"])
        self._validate_number_unique(values["controller_id"], values["port_number"])
        return self._commit(lambda: self.repository.create(values))

    def update(
        self, port_id: int, payload: CommunicationPortUpdate
    ) -> CommunicationPort:
        entity = self.get(port_id)
        values = payload.model_dump(exclude_unset=True)
        controller_id = values.get("controller_id", entity.controller_id)
        port_number = values.get("port_number", entity.port_number)
        self._validate_controller(controller_id)
        self._validate_number_unique(
            controller_id, port_number, exclude_id=entity.id
        )
        self._validate_attached_device_type(entity, values.get("port_type"))
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, port_id: int) -> CommunicationPort:
        entity = self.get(port_id)
        if self.repository.has_attached_devices(entity.id):
            raise BusinessRuleError(
                "Cannot deactivate a communication port with attached devices."
            )
        return self._commit(lambda: self.repository.deactivate(entity))

    def _validate_controller(self, controller_id: int) -> None:
        if self.controller_repository.get(controller_id) is None:
            raise NotFoundError("Controller not found.")

    def _validate_number_unique(
        self, controller_id: int, port_number: int, *, exclude_id: int | None = None
    ) -> None:
        existing = self.repository.get_by_controller_and_number(
            controller_id, port_number
        )
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("Port number already exists for this controller.")

    @staticmethod
    def _validate_attached_device_type(
        entity: CommunicationPort, proposed_type: PortType | None
    ) -> None:
        if proposed_type is None or proposed_type == entity.port_type:
            return
        if entity.pumps and proposed_type != PortType.PUMP:
            raise BusinessRuleError("A port with pumps must remain a PUMP port.")
        if entity.tank_probes and proposed_type != PortType.PROBE:
            raise BusinessRuleError("A port with probes must remain a PROBE port.")

    def _commit(self, operation: object) -> CommunicationPort:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
