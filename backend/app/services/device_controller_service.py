"""Business rules for station device controllers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.models.device_controller import DeviceController
from app.repositories.device_controller_repository import DeviceControllerRepository
from app.repositories.station_repository import StationRepository
from app.schemas.device_controller import DeviceControllerCreate, DeviceControllerUpdate


class DeviceControllerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DeviceControllerRepository(db)
        self.station_repository = StationRepository(db)

    def get(self, controller_id: int) -> DeviceController:
        entity = self.repository.get(controller_id)
        if entity is None:
            raise NotFoundError("Controller not found.")
        return entity

    def list(self) -> list[DeviceController]:
        return self.repository.list()

    def list_by_station(self, station_id: int) -> list[DeviceController]:
        self._validate_station(station_id)
        return self.repository.get_by_station(station_id)

    def create(self, payload: DeviceControllerCreate) -> DeviceController:
        values = payload.model_dump()
        self._validate_station(values["station_id"])
        self._validate_code_unique(values["station_id"], values["code"])
        return self._commit(lambda: self.repository.create(values))

    def update(
        self, controller_id: int, payload: DeviceControllerUpdate
    ) -> DeviceController:
        entity = self.get(controller_id)
        values = payload.model_dump(exclude_unset=True)
        station_id = values.get("station_id", entity.station_id)
        code = values.get("code", entity.code)
        self._validate_station(station_id)
        self._validate_code_unique(station_id, code, exclude_id=entity.id)
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, controller_id: int) -> DeviceController:
        return self._commit(lambda: self.repository.deactivate(self.get(controller_id)))

    def _validate_station(self, station_id: int) -> None:
        if self.station_repository.get(station_id) is None:
            raise NotFoundError("Station not found.")

    def _validate_code_unique(
        self, station_id: int, code: str, *, exclude_id: int | None = None
    ) -> None:
        existing = self.repository.get_by_station_and_code(station_id, code)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("Controller code already exists at this station.")

    def _commit(self, operation: object) -> DeviceController:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
