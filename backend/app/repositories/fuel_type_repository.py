"""Database queries for fuel types."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fuel_type import FuelType


class FuelTypeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, fuel_type_id: int) -> FuelType | None:
        return self.db.get(FuelType, fuel_type_id)

    def list(self) -> list[FuelType]:
        return list(self.db.scalars(select(FuelType).order_by(FuelType.name)))

    def get_by_code(self, code: str) -> FuelType | None:
        return self.db.scalar(select(FuelType).where(FuelType.code == code))

    def get_by_name(self, name: str) -> FuelType | None:
        return self.db.scalar(select(FuelType).where(FuelType.name == name))

    def create(self, values: dict[str, object]) -> FuelType:
        entity = FuelType(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: FuelType, values: dict[str, object]) -> FuelType:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: FuelType) -> FuelType:
        entity.is_active = False
        self.db.flush()
        return entity
