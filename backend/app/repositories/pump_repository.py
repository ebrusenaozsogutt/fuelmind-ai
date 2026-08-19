"""Database queries for pumps."""

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.alarm import Alarm
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.sensor_reading import SensorReading


class PumpRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, pump_id: int) -> Pump | None:
        return self.db.get(Pump, pump_id)

    def list(self) -> list[Pump]:
        return list(self.db.scalars(select(Pump).order_by(Pump.station_id, Pump.code)))

    def get_by_station_and_code(self, station_id: int, code: str) -> Pump | None:
        return self.db.scalar(
            select(Pump).where(Pump.station_id == station_id, Pump.code == code)
        )

    def get_by_port_and_device_address(
        self, communication_port_id: int, device_address: str
    ) -> Pump | None:
        return self.db.scalar(
            select(Pump).where(
                Pump.communication_port_id == communication_port_id,
                Pump.device_address == device_address,
            )
        )

    def create(self, values: dict[str, object]) -> Pump:
        entity = Pump(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Pump, values: dict[str, object]) -> Pump:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: Pump) -> Pump:
        entity.is_active = False
        self.db.flush()
        return entity

    def has_usage_history(self, pump_id: int) -> bool:
        return any(
            self.db.scalar(select(exists().where(model.pump_id == pump_id)))
            for model in (Sale, SensorReading, Alarm)
        )
