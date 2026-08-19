"""Business rules for customer authorized persons."""

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.commercial import CustomerAuthorizedPerson
from app.repositories.customer_authorized_person_repository import (
    CustomerAuthorizedPersonRepository,
)
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer_authorized_person import (
    CustomerAuthorizedPersonCreate,
    CustomerAuthorizedPersonUpdate,
)


class CustomerAuthorizedPersonService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CustomerAuthorizedPersonRepository(db)
        self.customer_repository = CustomerRepository(db)

    def get(self, person_id: int) -> CustomerAuthorizedPerson:
        entity = self.repository.get(person_id)
        if entity is None:
            raise NotFoundError("Authorized person not found.")
        return entity

    def list(self, *, customer_id: int | None = None) -> list[CustomerAuthorizedPerson]:
        if customer_id is not None:
            self._validate_customer(customer_id)
        return self.repository.list(customer_id=customer_id)

    def create(
        self, payload: CustomerAuthorizedPersonCreate
    ) -> CustomerAuthorizedPerson:
        values = payload.model_dump()
        self._validate_customer(values["customer_id"])
        self._validate_primary(
            customer_id=values["customer_id"],
            is_primary=values["is_primary"],
            is_active=values["is_active"],
        )
        return self._commit(lambda: self.repository.create(values))

    def update(
        self, person_id: int, payload: CustomerAuthorizedPersonUpdate
    ) -> CustomerAuthorizedPerson:
        entity = self.get(person_id)
        values = payload.model_dump(exclude_unset=True)
        customer_id = values.get("customer_id", entity.customer_id)
        self._validate_customer(customer_id)
        self._validate_primary(
            customer_id=customer_id,
            is_primary=values.get("is_primary", entity.is_primary),
            is_active=values.get("is_active", entity.is_active),
            exclude_id=entity.id,
        )
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, person_id: int) -> CustomerAuthorizedPerson:
        return self._commit(lambda: self.repository.deactivate(self.get(person_id)))

    def _validate_customer(self, customer_id: int) -> None:
        if self.customer_repository.get(customer_id) is None:
            raise NotFoundError("Customer not found.")

    def _validate_primary(
        self,
        *,
        customer_id: int,
        is_primary: bool,
        is_active: bool,
        exclude_id: int | None = None,
    ) -> None:
        if not is_primary or not is_active:
            return
        existing = self.repository.get_primary_for_customer(customer_id)
        if existing is not None and existing.id != exclude_id:
            raise BusinessRuleError("Customer already has a primary authorized person.")

    def _commit(self, operation: object) -> CustomerAuthorizedPerson:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
