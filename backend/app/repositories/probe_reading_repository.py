"""Read-only database queries for historical probe readings."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.probe_reading import ProbeReading


class ProbeReadingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_probe(
        self,
        probe_id: int,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[ProbeReading]:
        statement = select(ProbeReading).where(ProbeReading.probe_id == probe_id)
        if start is not None:
            statement = statement.where(ProbeReading.reading_timestamp >= start)
        if end is not None:
            statement = statement.where(ProbeReading.reading_timestamp <= end)
        statement = statement.order_by(ProbeReading.reading_timestamp.desc()).limit(limit)
        return list(self.db.scalars(statement))

    def list_by_tank(
        self,
        tank_id: int,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[ProbeReading]:
        statement = select(ProbeReading).where(ProbeReading.tank_id == tank_id)
        if start is not None:
            statement = statement.where(ProbeReading.reading_timestamp >= start)
        if end is not None:
            statement = statement.where(ProbeReading.reading_timestamp <= end)
        statement = statement.order_by(ProbeReading.reading_timestamp.desc()).limit(limit)
        return list(self.db.scalars(statement))
