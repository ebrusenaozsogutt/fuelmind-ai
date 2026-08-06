"""Business rules for stations."""

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.models.station import Station
from app.repositories.station_repository import StationRepository
from app.schemas.station import StationCreate, StationUpdate


class StationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = StationRepository(db)

    def get(self, station_id: int) -> Station:
        entity = self.repository.get(station_id)
        if entity is None:
            raise NotFoundError("Station not found.")
        return entity

    def list(self) -> list[Station]:
        return self.repository.list()

    def create(self, payload: StationCreate) -> Station:
        values = payload.model_dump()
        if self.repository.get_by_code(values["code"]):
            raise ConflictError("Station code already exists.")
        return self._commit(lambda: self.repository.create(values))

    def update(self, station_id: int, payload: StationUpdate) -> Station:
        entity = self.get(station_id)
        values = payload.model_dump(exclude_unset=True)
        code = values.get("code")
        if (
            code
            and (existing := self.repository.get_by_code(code))
            and existing.id != entity.id
        ):
            raise ConflictError("Station code already exists.")
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, station_id: int) -> Station:
        """Soft-delete a station; history is always retained."""
        return self._commit(lambda: self.repository.deactivate(self.get(station_id)))

    def _commit(self, operation: object) -> Station:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
