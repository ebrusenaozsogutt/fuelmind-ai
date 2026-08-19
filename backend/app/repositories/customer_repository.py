"""Database queries for commercial customers."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.commercial import Customer
from app.utils.enums import CustomerRequestStatus, CustomerType


class CustomerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, customer_id: int) -> Customer | None:
        return self.db.get(Customer, customer_id)

    def get_by_code(self, code: str) -> Customer | None:
        return self.db.scalar(select(Customer).where(Customer.code == code))

    def list(
        self,
        *,
        customer_type: CustomerType | None = None,
        is_active: bool | None = None,
        request_status: CustomerRequestStatus | None = None,
        sector: str | None = None,
        search: str | None = None,
    ) -> list[Customer]:
        statement = select(Customer)
        if customer_type is not None:
            statement = statement.where(Customer.customer_type == customer_type)
        if is_active is not None:
            statement = statement.where(Customer.is_active == is_active)
        if request_status is not None:
            statement = statement.where(Customer.request_status == request_status)
        if sector is not None:
            statement = statement.where(Customer.sector == sector)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    Customer.code.ilike(pattern),
                    Customer.name.ilike(pattern),
                    Customer.tax_number.ilike(pattern),
                )
            )
        return list(self.db.scalars(statement.order_by(Customer.code)))

    def create(self, values: dict[str, object]) -> Customer:
        entity = Customer(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Customer, values: dict[str, object]) -> Customer:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: Customer) -> Customer:
        entity.is_active = False
        self.db.flush()
        return entity
