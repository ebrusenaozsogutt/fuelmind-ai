"""Business rules for commercial fleet groups."""

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.commercial import FleetGroup
from app.repositories.fleet_group_repository import FleetGroupRepository
from app.repositories.fleet_repository import FleetRepository
from app.schemas.fleet_group import FleetGroupCreate, FleetGroupUpdate


class FleetGroupService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = FleetGroupRepository(db)
        self.fleet_repository = FleetRepository(db)

    def get(self, group_id: int) -> FleetGroup:
        entity = self.repository.get(group_id)
        if entity is None:
            raise NotFoundError("Fleet group not found.")
        return entity

    def list(
        self, *, fleet_id: int | None = None, is_active: bool | None = None
    ) -> list[FleetGroup]:
        if fleet_id is not None:
            self._validate_fleet(fleet_id)
        return self.repository.list(fleet_id=fleet_id, is_active=is_active)

    def create(self, payload: FleetGroupCreate) -> FleetGroup:
        values = payload.model_dump()
        self._validate_fleet(values["fleet_id"], require_active=values["is_active"])
        self._validate_unique_code(values["fleet_id"], values["code"])
        return self._commit(lambda: self.repository.create(values))

    def update(self, group_id: int, payload: FleetGroupUpdate) -> FleetGroup:
        entity = self.get(group_id)
        values = payload.model_dump(exclude_unset=True)
        fleet_id = values.get("fleet_id", entity.fleet_id)
        is_active = values.get("is_active", entity.is_active)
        self._validate_fleet(fleet_id, require_active=is_active)
        self._validate_unique_code(
            fleet_id, values.get("code", entity.code), exclude_id=entity.id
        )
        if values.get("is_active") is False and self.repository.has_active_vehicles(entity.id):
            raise BusinessRuleError(
                "Fleet group has active vehicles and cannot be deactivated."
            )
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, group_id: int) -> FleetGroup:
        entity = self.get(group_id)
        if self.repository.has_active_vehicles(entity.id):
            raise BusinessRuleError(
                "Fleet group has active vehicles and cannot be deactivated."
            )
        return self._commit(lambda: self.repository.deactivate(entity))

    def _validate_fleet(self, fleet_id: int, *, require_active: bool = False) -> None:
        fleet = self.fleet_repository.get(fleet_id)
        if fleet is None:
            raise NotFoundError("Fleet not found.")
        if require_active and not fleet.is_active:
            raise BusinessRuleError("Cannot create an active group for an inactive fleet.")

    def _validate_unique_code(
        self, fleet_id: int, code: str, *, exclude_id: int | None = None
    ) -> None:
        existing = self.repository.get_by_fleet_and_code(fleet_id, code)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("Fleet group code already exists for this fleet.")

    def _commit(self, operation: object) -> FleetGroup:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
