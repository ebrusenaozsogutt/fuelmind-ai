"""Database queries for driver vehicle assignments."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commercial import DriverVehicleAssignment
from app.utils.enums import DriverAssignmentStatus


class DriverVehicleAssignmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, assignment_id: int) -> DriverVehicleAssignment | None:
        return self.db.get(DriverVehicleAssignment, assignment_id)

    def list(
        self, *, driver_id: int | None = None, vehicle_id: int | None = None
    ) -> list[DriverVehicleAssignment]:
        statement = select(DriverVehicleAssignment)
        if driver_id is not None:
            statement = statement.where(DriverVehicleAssignment.driver_id == driver_id)
        if vehicle_id is not None:
            statement = statement.where(DriverVehicleAssignment.vehicle_id == vehicle_id)
        return list(self.db.scalars(statement.order_by(DriverVehicleAssignment.assigned_from)))

    def list_active_for_driver_or_vehicle(
        self, *, driver_id: int, vehicle_id: int
    ) -> list[DriverVehicleAssignment]:
        return list(
            self.db.scalars(
                select(DriverVehicleAssignment).where(
                    DriverVehicleAssignment.status == DriverAssignmentStatus.ACTIVE,
                    (DriverVehicleAssignment.driver_id == driver_id)
                    | (DriverVehicleAssignment.vehicle_id == vehicle_id),
                )
            )
        )

    def current_for_vehicle(
        self, vehicle_id: int, on_date: date
    ) -> DriverVehicleAssignment | None:
        return self.db.scalar(
            select(DriverVehicleAssignment)
            .where(
                DriverVehicleAssignment.vehicle_id == vehicle_id,
                DriverVehicleAssignment.status == DriverAssignmentStatus.ACTIVE,
                DriverVehicleAssignment.assigned_from <= on_date,
                (DriverVehicleAssignment.assigned_until.is_(None))
                | (DriverVehicleAssignment.assigned_until > on_date),
            )
            .order_by(DriverVehicleAssignment.assigned_from.desc())
        )

    def create(self, values: dict[str, object]) -> DriverVehicleAssignment:
        entity = DriverVehicleAssignment(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(
        self, entity: DriverVehicleAssignment, values: dict[str, object]
    ) -> DriverVehicleAssignment:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def cancel(self, entity: DriverVehicleAssignment) -> DriverVehicleAssignment:
        entity.status = DriverAssignmentStatus.CANCELLED
        self.db.flush()
        return entity
