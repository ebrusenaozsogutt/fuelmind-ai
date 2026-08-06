"""Database queries for tanks."""

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.alarm import Alarm
from app.models.delivery import Delivery
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.sensor_reading import SensorReading
from app.models.tank import Tank


class TankRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, tank_id: int) -> Tank | None:
        return self.db.get(Tank, tank_id)

    def get_for_update(self, tank_id: int) -> Tank | None:
        return self.db.scalar(select(Tank).where(Tank.id == tank_id).with_for_update())

    def list(self) -> list[Tank]:
        return list(self.db.scalars(select(Tank).order_by(Tank.station_id, Tank.code)))

    def get_by_station_and_code(self, station_id: int, code: str) -> Tank | None:
        return self.db.scalar(
            select(Tank).where(Tank.station_id == station_id, Tank.code == code)
        )

    def create(self, values: dict[str, object]) -> Tank:
        entity = Tank(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Tank, values: dict[str, object]) -> Tank:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: Tank) -> Tank:
        entity.is_active = False
        self.db.flush()
        return entity

    def has_usage_history(self, tank_id: int) -> bool:
        statements = (Pump, Sale, SensorReading, Delivery, Alarm)
        return any(
            self.db.scalar(select(exists().where(model.tank_id == tank_id)))
            for model in statements
        )
