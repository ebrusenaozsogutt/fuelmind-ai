"""Database queries for stations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.station import Station


class StationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, station_id: int) -> Station | None:
        return self.db.get(Station, station_id)

    def list(self) -> list[Station]:
        return list(self.db.scalars(select(Station).order_by(Station.code)))

    def get_by_code(self, code: str) -> Station | None:
        return self.db.scalar(select(Station).where(Station.code == code))

    def create(self, values: dict[str, object]) -> Station:
        entity = Station(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Station, values: dict[str, object]) -> Station:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: Station) -> Station:
        entity.is_active = False
        self.db.flush()
        return entity
