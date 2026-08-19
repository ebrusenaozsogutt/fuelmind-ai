"""Business rules for drivers."""

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.commercial import Driver
from app.repositories.driver_repository import DriverRepository
from app.schemas.driver import DriverCreate, DriverUpdate


class DriverService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DriverRepository(db)

    def get(self, driver_id: int) -> Driver:
        entity = self.repository.get(driver_id)
        if entity is None:
            raise NotFoundError("Driver not found.")
        return entity

    def list(
        self, *, is_active: bool | None = None, search: str | None = None
    ) -> list[Driver]:
        return self.repository.list(
            is_active=is_active, search=search.strip() if search else None
        )

    def create(self, payload: DriverCreate) -> Driver:
        values = payload.model_dump()
        self._validate_unique_reference_code(values["reference_code"])
        return self._commit(lambda: self.repository.create(values))

    def update(self, driver_id: int, payload: DriverUpdate) -> Driver:
        entity = self.get(driver_id)
        values = payload.model_dump(exclude_unset=True)
        if "reference_code" in values:
            self._validate_unique_reference_code(
                values["reference_code"], exclude_id=entity.id
            )
        if values.get("is_active") is False and self.repository.has_active_assignments(
            entity.id
        ):
            raise BusinessRuleError("Driver has active vehicle assignments.")
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, driver_id: int) -> Driver:
        entity = self.get(driver_id)
        if self.repository.has_active_assignments(entity.id):
            raise BusinessRuleError("Driver has active vehicle assignments.")
        return self._commit(lambda: self.repository.deactivate(entity))

    def _validate_unique_reference_code(
        self, reference_code: str | None, *, exclude_id: int | None = None
    ) -> None:
        if reference_code is None:
            return
        existing = self.repository.get_by_reference_code(reference_code)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("Driver reference code already exists.")

    def _commit(self, operation: object) -> Driver:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
