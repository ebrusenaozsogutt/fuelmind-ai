"""Database queries for device controllers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device_controller import DeviceController


class DeviceControllerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, controller_id: int) -> DeviceController | None:
        return self.db.get(DeviceController, controller_id)

    def list(self) -> list[DeviceController]:
        statement = select(DeviceController).order_by(
            DeviceController.station_id, DeviceController.code
        )
        return list(self.db.scalars(statement))

    def get_by_station_and_code(
        self, station_id: int, code: str
    ) -> DeviceController | None:
        return self.db.scalar(
            select(DeviceController).where(
                DeviceController.station_id == station_id,
                DeviceController.code == code,
            )
        )

    def get_by_station(self, station_id: int) -> list[DeviceController]:
        statement = select(DeviceController).where(
            DeviceController.station_id == station_id
        ).order_by(DeviceController.code)
        return list(self.db.scalars(statement))

    def create(self, values: dict[str, object]) -> DeviceController:
        entity = DeviceController(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(
        self, entity: DeviceController, values: dict[str, object]
    ) -> DeviceController:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: DeviceController) -> DeviceController:
        entity.is_active = False
        self.db.flush()
        return entity
