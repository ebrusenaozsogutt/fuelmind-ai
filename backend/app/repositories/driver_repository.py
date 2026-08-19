"""Database queries for drivers."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.commercial import Driver, DriverVehicleAssignment
from app.utils.enums import DriverAssignmentStatus


class DriverRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, driver_id: int) -> Driver | None:
        return self.db.get(Driver, driver_id)

    def get_by_reference_code(self, reference_code: str) -> Driver | None:
        return self.db.scalar(
            select(Driver).where(Driver.reference_code == reference_code)
        )

    def list(
        self, *, is_active: bool | None = None, search: str | None = None
    ) -> list[Driver]:
        statement = select(Driver)
        if is_active is not None:
            statement = statement.where(Driver.is_active == is_active)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    Driver.full_name.ilike(pattern),
                    Driver.reference_code.ilike(pattern),
                    Driver.license_number.ilike(pattern),
                )
            )
        return list(self.db.scalars(statement.order_by(Driver.full_name)))

    def has_active_assignments(self, driver_id: int) -> bool:
        return self.db.scalar(
            select(DriverVehicleAssignment.id).where(
                DriverVehicleAssignment.driver_id == driver_id,
                DriverVehicleAssignment.status == DriverAssignmentStatus.ACTIVE,
            ).limit(1)
        ) is not None

    def create(self, values: dict[str, object]) -> Driver:
        entity = Driver(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Driver, values: dict[str, object]) -> Driver:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: Driver) -> Driver:
        entity.is_active = False
        self.db.flush()
        return entity
