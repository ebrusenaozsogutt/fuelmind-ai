"""Database queries for commercial vehicles."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.commercial import (
    DriverVehicleAssignment,
    FuelCard,
    Vehicle,
)
from app.utils.enums import CardStatus, DriverAssignmentStatus


class VehicleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, vehicle_id: int) -> Vehicle | None:
        return self.db.get(Vehicle, vehicle_id)

    def get_by_plate(self, plate: str) -> Vehicle | None:
        return self.db.scalar(select(Vehicle).where(Vehicle.plate == plate))

    def list(
        self,
        *,
        fleet_group_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[Vehicle]:
        statement = select(Vehicle)
        if fleet_group_id is not None:
            statement = statement.where(Vehicle.fleet_group_id == fleet_group_id)
        if is_active is not None:
            statement = statement.where(Vehicle.is_active == is_active)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    Vehicle.plate.ilike(pattern),
                    Vehicle.brand.ilike(pattern),
                    Vehicle.model.ilike(pattern),
                )
            )
        return list(self.db.scalars(statement.order_by(Vehicle.plate)))

    def has_active_fuel_cards(self, vehicle_id: int) -> bool:
        return self.db.scalar(
            select(FuelCard.id).where(
                FuelCard.vehicle_id == vehicle_id,
                FuelCard.is_active.is_(True),
                FuelCard.status == CardStatus.ACTIVE,
            ).limit(1)
        ) is not None

    def has_any_fuel_cards(self, vehicle_id: int) -> bool:
        return self.db.scalar(
            select(FuelCard.id).where(FuelCard.vehicle_id == vehicle_id).limit(1)
        ) is not None

    def has_active_assignments(self, vehicle_id: int) -> bool:
        return self.db.scalar(
            select(DriverVehicleAssignment.id).where(
                DriverVehicleAssignment.vehicle_id == vehicle_id,
                DriverVehicleAssignment.status == DriverAssignmentStatus.ACTIVE,
            ).limit(1)
        ) is not None

    def create(self, values: dict[str, object]) -> Vehicle:
        entity = Vehicle(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Vehicle, values: dict[str, object]) -> Vehicle:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: Vehicle) -> Vehicle:
        entity.is_active = False
        self.db.flush()
        return entity
