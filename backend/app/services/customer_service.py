"""Business rules for commercial customers."""

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.models.commercial import Customer
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.utils.enums import CustomerRequestStatus, CustomerType


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CustomerRepository(db)

    def get(self, customer_id: int) -> Customer:
        entity = self.repository.get(customer_id)
        if entity is None:
            raise NotFoundError("Customer not found.")
        return entity

    def list(
        self,
        *,
        customer_type: CustomerType | None = None,
        is_active: bool | None = None,
        request_status: CustomerRequestStatus | None = None,
        sector: str | None = None,
        search: str | None = None,
    ) -> list[Customer]:
        return self.repository.list(
            customer_type=customer_type,
            is_active=is_active,
            request_status=request_status,
            sector=sector,
            search=search.strip() if search else None,
        )

    def create(self, payload: CustomerCreate) -> Customer:
        values = payload.model_dump()
        if values["registration_date"] is None:
            values.pop("registration_date")
        self._validate_unique_code(values["code"])
        return self._commit(lambda: self.repository.create(values))

    def update(self, customer_id: int, payload: CustomerUpdate) -> Customer:
        entity = self.get(customer_id)
        values = payload.model_dump(exclude_unset=True)
        if values.get("registration_date") is None:
            values.pop("registration_date", None)
        code = values.get("code")
        if code is not None:
            self._validate_unique_code(code, exclude_id=entity.id)
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, customer_id: int) -> Customer:
        return self._commit(lambda: self.repository.deactivate(self.get(customer_id)))

    def _validate_unique_code(self, code: str, *, exclude_id: int | None = None) -> None:
        existing = self.repository.get_by_code(code)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("Customer code already exists.")

    def _commit(self, operation: object) -> Customer:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
