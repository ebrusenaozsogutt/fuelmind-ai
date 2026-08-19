"""Business rules for commercial fleets."""

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.commercial import Fleet
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fleet_repository import FleetRepository
from app.schemas.fleet import FleetCreate, FleetUpdate
from app.utils.enums import CustomerRequestStatus


class FleetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = FleetRepository(db)
        self.customer_repository = CustomerRepository(db)

    def get(self, fleet_id: int) -> Fleet:
        entity = self.repository.get(fleet_id)
        if entity is None:
            raise NotFoundError("Fleet not found.")
        return entity

    def list(
        self,
        *,
        customer_id: int | None = None,
        request_status: CustomerRequestStatus | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[Fleet]:
        if customer_id is not None:
            self._validate_customer(customer_id)
        return self.repository.list(
            customer_id=customer_id,
            request_status=request_status,
            is_active=is_active,
            search=search.strip() if search else None,
        )

    def create(self, payload: FleetCreate) -> Fleet:
        values = payload.model_dump()
        self._validate_customer(values["customer_id"], require_active=values["is_active"])
        self._validate_unique_code(values["customer_id"], values["code"])
        return self._commit(lambda: self.repository.create(values))

    def update(self, fleet_id: int, payload: FleetUpdate) -> Fleet:
        entity = self.get(fleet_id)
        values = payload.model_dump(exclude_unset=True)
        customer_id = values.get("customer_id", entity.customer_id)
        is_active = values.get("is_active", entity.is_active)
        self._validate_customer(customer_id, require_active=is_active)
        self._validate_unique_code(
            customer_id, values.get("code", entity.code), exclude_id=entity.id
        )
        if values.get("is_active") is False and self.repository.has_active_groups(entity.id):
            raise BusinessRuleError("Fleet has active groups and cannot be deactivated.")
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, fleet_id: int) -> Fleet:
        entity = self.get(fleet_id)
        if self.repository.has_active_groups(entity.id):
            raise BusinessRuleError("Fleet has active groups and cannot be deactivated.")
        return self._commit(lambda: self.repository.deactivate(entity))

    def _validate_customer(self, customer_id: int, *, require_active: bool = False) -> None:
        customer = self.customer_repository.get(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.")
        if require_active and not customer.is_active:
            raise BusinessRuleError("Cannot create an active fleet for an inactive customer.")

    def _validate_unique_code(
        self, customer_id: int, code: str, *, exclude_id: int | None = None
    ) -> None:
        existing = self.repository.get_by_customer_and_code(customer_id, code)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("Fleet code already exists for this customer.")

    def _commit(self, operation: object) -> Fleet:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
