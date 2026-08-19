"""Database queries for customer authorized persons."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commercial import CustomerAuthorizedPerson


class CustomerAuthorizedPersonRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, person_id: int) -> CustomerAuthorizedPerson | None:
        return self.db.get(CustomerAuthorizedPerson, person_id)

    def list(self, *, customer_id: int | None = None) -> list[CustomerAuthorizedPerson]:
        statement = select(CustomerAuthorizedPerson)
        if customer_id is not None:
            statement = statement.where(CustomerAuthorizedPerson.customer_id == customer_id)
        return list(self.db.scalars(statement.order_by(CustomerAuthorizedPerson.full_name)))

    def get_primary_for_customer(
        self, customer_id: int
    ) -> CustomerAuthorizedPerson | None:
        return self.db.scalar(
            select(CustomerAuthorizedPerson).where(
                CustomerAuthorizedPerson.customer_id == customer_id,
                CustomerAuthorizedPerson.is_primary.is_(True),
                CustomerAuthorizedPerson.is_active.is_(True),
            )
        )

    def create(self, values: dict[str, object]) -> CustomerAuthorizedPerson:
        entity = CustomerAuthorizedPerson(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(
        self, entity: CustomerAuthorizedPerson, values: dict[str, object]
    ) -> CustomerAuthorizedPerson:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: CustomerAuthorizedPerson) -> CustomerAuthorizedPerson:
        entity.is_active = False
        self.db.flush()
        return entity
