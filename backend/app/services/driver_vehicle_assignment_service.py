"""Business rules for historical, non-overlapping driver assignments."""

from datetime import date

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.commercial import DriverVehicleAssignment
from app.repositories.customer_repository import CustomerRepository
from app.repositories.driver_repository import DriverRepository
from app.repositories.driver_vehicle_assignment_repository import (
    DriverVehicleAssignmentRepository,
)
from app.repositories.fleet_group_repository import FleetGroupRepository
from app.repositories.fleet_repository import FleetRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.driver_vehicle_assignment import (
    DriverVehicleAssignmentCreate,
    DriverVehicleAssignmentUpdate,
)
from app.utils.datetime_utils import utc_now
from app.utils.enums import DriverAssignmentStatus


class DriverVehicleAssignmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DriverVehicleAssignmentRepository(db)
        self.driver_repository = DriverRepository(db)
        self.vehicle_repository = VehicleRepository(db)
        self.fleet_group_repository = FleetGroupRepository(db)
        self.fleet_repository = FleetRepository(db)
        self.customer_repository = CustomerRepository(db)

    def get(self, assignment_id: int) -> DriverVehicleAssignment:
        entity = self.repository.get(assignment_id)
        if entity is None:
            raise NotFoundError("Driver vehicle assignment not found.")
        return entity

    def list(
        self, *, driver_id: int | None = None, vehicle_id: int | None = None
    ) -> list[DriverVehicleAssignment]:
        if driver_id is not None and self.driver_repository.get(driver_id) is None:
            raise NotFoundError("Driver not found.")
        if vehicle_id is not None and self.vehicle_repository.get(vehicle_id) is None:
            raise NotFoundError("Vehicle not found.")
        return self.repository.list(driver_id=driver_id, vehicle_id=vehicle_id)

    def create(
        self, payload: DriverVehicleAssignmentCreate
    ) -> DriverVehicleAssignment:
        values = payload.model_dump()
        self._validate_assignment(**values)
        return self._commit(lambda: self.repository.create(values))

    def update(
        self, assignment_id: int, payload: DriverVehicleAssignmentUpdate
    ) -> DriverVehicleAssignment:
        entity = self.get(assignment_id)
        values = payload.model_dump(exclude_unset=True)
        combined = {
            "driver_id": values.get("driver_id", entity.driver_id),
            "vehicle_id": values.get("vehicle_id", entity.vehicle_id),
            "assigned_from": values.get("assigned_from", entity.assigned_from),
            "assigned_until": values.get("assigned_until", entity.assigned_until),
            "status": values.get("status", entity.status),
        }
        self._validate_assignment(**combined, exclude_id=entity.id)
        return self._commit(lambda: self.repository.update(entity, values))

    def cancel(self, assignment_id: int) -> DriverVehicleAssignment:
        return self._commit(lambda: self.repository.cancel(self.get(assignment_id)))

    def current_for_vehicle(self, vehicle_id: int) -> DriverVehicleAssignment | None:
        if self.vehicle_repository.get(vehicle_id) is None:
            raise NotFoundError("Vehicle not found.")
        return self.repository.current_for_vehicle(vehicle_id, utc_now().date())

    def _validate_assignment(
        self,
        *,
        driver_id: int,
        vehicle_id: int,
        assigned_from: date,
        assigned_until: date | None,
        status: DriverAssignmentStatus,
        exclude_id: int | None = None,
    ) -> None:
        if assigned_until is not None and assigned_until < assigned_from:
            raise BusinessRuleError("Assignment end date cannot precede start date.")
        if status != DriverAssignmentStatus.ACTIVE:
            return
        self._validate_active_driver(driver_id)
        self._validate_active_vehicle_hierarchy(vehicle_id)
        for existing in self.repository.list_active_for_driver_or_vehicle(
            driver_id=driver_id, vehicle_id=vehicle_id
        ):
            if existing.id == exclude_id or not self._overlaps(
                existing.assigned_from,
                existing.assigned_until,
                assigned_from,
                assigned_until,
            ):
                continue
            if existing.vehicle_id == vehicle_id:
                raise BusinessRuleError(
                    "Vehicle already has another driver in requested time range."
                )
            raise BusinessRuleError("Driver assignment overlaps an existing assignment.")

    def _validate_active_driver(self, driver_id: int) -> None:
        driver = self.driver_repository.get(driver_id)
        if driver is None:
            raise NotFoundError("Driver not found.")
        if not driver.is_active:
            raise BusinessRuleError("Driver is inactive.")

    def _validate_active_vehicle_hierarchy(self, vehicle_id: int) -> None:
        vehicle = self.vehicle_repository.get(vehicle_id)
        if vehicle is None:
            raise NotFoundError("Vehicle not found.")
        if not vehicle.is_active:
            raise BusinessRuleError("Vehicle is inactive.")
        group = self.fleet_group_repository.get(vehicle.fleet_group_id)
        if group is None:
            raise NotFoundError("Fleet group not found.")
        fleet = self.fleet_repository.get(group.fleet_id)
        if fleet is None:
            raise NotFoundError("Fleet not found.")
        customer = self.customer_repository.get(fleet.customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.")
        if not group.is_active or not fleet.is_active or not customer.is_active:
            raise BusinessRuleError("Vehicle hierarchy is inactive.")

    @staticmethod
    def _overlaps(
        first_start: date,
        first_end: date | None,
        second_start: date,
        second_end: date | None,
    ) -> bool:
        """Use half-open intervals so a boundary handoff remains valid."""

        return (second_end is None or first_start < second_end) and (
            first_end is None or second_start < first_end
        )

    def _commit(self, operation: object) -> DriverVehicleAssignment:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
