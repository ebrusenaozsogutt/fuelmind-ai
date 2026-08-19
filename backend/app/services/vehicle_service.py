"""Business rules for commercial vehicles."""

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.commercial import FleetGroup, Vehicle
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fleet_group_repository import FleetGroupRepository
from app.repositories.fleet_repository import FleetRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from sqlalchemy.orm import Session


class VehicleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = VehicleRepository(db)
        self.fleet_group_repository = FleetGroupRepository(db)
        self.fleet_repository = FleetRepository(db)
        self.customer_repository = CustomerRepository(db)

    def get(self, vehicle_id: int) -> Vehicle:
        entity = self.repository.get(vehicle_id)
        if entity is None:
            raise NotFoundError("Vehicle not found.")
        return entity

    def list(
        self,
        *,
        fleet_group_id: int | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[Vehicle]:
        if fleet_group_id is not None:
            self._get_fleet_group(fleet_group_id)
        return self.repository.list(
            fleet_group_id=fleet_group_id,
            is_active=is_active,
            search=search.strip() if search else None,
        )

    def create(self, payload: VehicleCreate) -> Vehicle:
        values = payload.model_dump()
        values["plate"] = self.normalize_plate(values["plate"])
        self._validate_hierarchy(values["fleet_group_id"], require_active=values["is_active"])
        self._validate_unique_plate(values["plate"])
        return self._commit(lambda: self.repository.create(values))

    def update(self, vehicle_id: int, payload: VehicleUpdate) -> Vehicle:
        entity = self.get(vehicle_id)
        values = payload.model_dump(exclude_unset=True)
        fleet_group_id = values.get("fleet_group_id", entity.fleet_group_id)
        is_active = values.get("is_active", entity.is_active)
        if "plate" in values:
            values["plate"] = self.normalize_plate(values["plate"])
            self._validate_unique_plate(values["plate"], exclude_id=entity.id)
        self._validate_hierarchy(fleet_group_id, require_active=is_active)
        if fleet_group_id != entity.fleet_group_id:
            if self.repository.has_any_fuel_cards(entity.id):
                raise BusinessRuleError("Vehicle with fuel cards cannot change fleet group.")
            if self.repository.has_active_assignments(entity.id):
                raise BusinessRuleError(
                    "Vehicle with active driver assignments cannot change fleet group."
                )
        if values.get("is_active") is False:
            self._validate_safe_deactivate(entity.id)
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, vehicle_id: int) -> Vehicle:
        entity = self.get(vehicle_id)
        self._validate_safe_deactivate(entity.id)
        return self._commit(lambda: self.repository.deactivate(entity))

    @staticmethod
    def normalize_plate(value: str) -> str:
        """Normalize whitespace and casing without imposing a country-specific format."""

        return " ".join(value.split()).upper()

    def _get_fleet_group(self, fleet_group_id: int) -> FleetGroup:
        group = self.fleet_group_repository.get(fleet_group_id)
        if group is None:
            raise NotFoundError("Fleet group not found.")
        return group

    def _validate_hierarchy(self, fleet_group_id: int, *, require_active: bool) -> None:
        group = self._get_fleet_group(fleet_group_id)
        fleet = self.fleet_repository.get(group.fleet_id)
        if fleet is None:
            raise NotFoundError("Fleet not found.")
        customer = self.customer_repository.get(fleet.customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.")
        if require_active and not group.is_active:
            raise BusinessRuleError("Fleet group is inactive.")
        if require_active and not fleet.is_active:
            raise BusinessRuleError("Vehicle hierarchy fleet is inactive.")
        if require_active and not customer.is_active:
            raise BusinessRuleError("Vehicle hierarchy customer is inactive.")

    def _validate_unique_plate(self, plate: str, *, exclude_id: int | None = None) -> None:
        existing = self.repository.get_by_plate(plate)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("Vehicle plate already exists.")

    def _validate_safe_deactivate(self, vehicle_id: int) -> None:
        if self.repository.has_active_fuel_cards(vehicle_id):
            raise BusinessRuleError("Vehicle has an active fuel card.")
        if self.repository.has_active_assignments(vehicle_id):
            raise BusinessRuleError("Vehicle has an active driver assignment.")

    def _commit(self, operation: object) -> Vehicle:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
