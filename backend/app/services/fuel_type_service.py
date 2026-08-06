"""Business rules for fuel types."""

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.models.fuel_type import FuelType
from app.repositories.fuel_type_repository import FuelTypeRepository
from app.schemas.fuel_type import FuelTypeCreate, FuelTypeUpdate


class FuelTypeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = FuelTypeRepository(db)

    def get(self, fuel_type_id: int) -> FuelType:
        entity = self.repository.get(fuel_type_id)
        if entity is None:
            raise NotFoundError("Fuel type not found.")
        return entity

    def list(self) -> list[FuelType]:
        return self.repository.list()

    def create(self, payload: FuelTypeCreate) -> FuelType:
        values = payload.model_dump()
        if self.repository.get_by_code(values["code"]) or self.repository.get_by_name(
            values["name"]
        ):
            raise ConflictError("Fuel type name and code must be unique.")
        return self._commit(lambda: self.repository.create(values))

    def update(self, fuel_type_id: int, payload: FuelTypeUpdate) -> FuelType:
        entity = self.get(fuel_type_id)
        values = payload.model_dump(exclude_unset=True)
        code = values.get("code")
        name = values.get("name")
        if (
            code
            and (existing := self.repository.get_by_code(code))
            and existing.id != entity.id
        ):
            raise ConflictError("Fuel type code already exists.")
        if (
            name
            and (existing := self.repository.get_by_name(name))
            and existing.id != entity.id
        ):
            raise ConflictError("Fuel type name already exists.")
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, fuel_type_id: int) -> FuelType:
        return self._commit(lambda: self.repository.deactivate(self.get(fuel_type_id)))

    def _commit(self, operation: object) -> FuelType:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
