"""Read-only, indexed history queries for sensor readings."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sensor_reading import SensorReading


class SensorReadingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def history(self, *, station_id: int | None = None, tank_id: int | None = None, pump_id: int | None = None, simulation_run_id: int | None = None, from_time: datetime, to_time: datetime, limit: int) -> list[SensorReading]:
        statement = select(SensorReading).where(SensorReading.reading_timestamp >= from_time, SensorReading.reading_timestamp <= to_time)
        if station_id is not None:
            statement = statement.where(SensorReading.station_id == station_id)
        if tank_id is not None:
            statement = statement.where(SensorReading.tank_id == tank_id)
        if pump_id is not None:
            statement = statement.where(SensorReading.pump_id == pump_id)
        if simulation_run_id is not None:
            statement = statement.where(SensorReading.simulation_run_id == simulation_run_id)
        readings = list(self.db.scalars(statement.order_by(SensorReading.reading_timestamp.desc()).limit(limit)))
        readings.reverse()
        return readings

    def latest_for_target(self, *, tank_id: int, pump_id: int | None) -> SensorReading | None:
        statement = select(SensorReading).where(SensorReading.tank_id == tank_id)
        statement = statement.where(SensorReading.pump_id == pump_id) if pump_id is not None else statement.where(SensorReading.pump_id.is_(None))
        return self.db.scalar(statement.order_by(SensorReading.reading_timestamp.desc()).limit(1))
