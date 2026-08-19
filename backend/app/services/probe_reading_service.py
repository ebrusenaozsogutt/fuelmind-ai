"""Read-only access rules for historical probe readings."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.probe_reading import ProbeReading
from app.repositories.probe_reading_repository import ProbeReadingRepository
from app.repositories.tank_probe_repository import TankProbeRepository
from app.repositories.tank_repository import TankRepository


class ProbeReadingService:
    def __init__(self, db: Session) -> None:
        self.repository = ProbeReadingRepository(db)
        self.probe_repository = TankProbeRepository(db)
        self.tank_repository = TankRepository(db)

    def list_by_probe(
        self,
        probe_id: int,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[ProbeReading]:
        if self.probe_repository.get(probe_id) is None:
            raise NotFoundError("Tank probe not found.")
        self._validate_range(start, end)
        return self.repository.list_by_probe(probe_id, start, end, limit)

    def list_by_tank(
        self,
        tank_id: int,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[ProbeReading]:
        if self.tank_repository.get(tank_id) is None:
            raise NotFoundError("Tank not found.")
        self._validate_range(start, end)
        return self.repository.list_by_tank(tank_id, start, end, limit)

    @staticmethod
    def _validate_range(start: datetime | None, end: datetime | None) -> None:
        if start is not None and end is not None and start > end:
            raise BusinessRuleError("start must not be later than end.")
