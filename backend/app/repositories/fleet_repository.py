"""Database queries for commercial fleets."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.commercial import Fleet
from app.utils.enums import CustomerRequestStatus


class FleetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, fleet_id: int) -> Fleet | None:
        return self.db.get(Fleet, fleet_id)

    def get_by_customer_and_code(self, customer_id: int, code: str) -> Fleet | None:
        return self.db.scalar(
            select(Fleet).where(Fleet.customer_id == customer_id, Fleet.code == code)
        )

    def list(
        self,
        *,
        customer_id: int | None = None,
        request_status: CustomerRequestStatus | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[Fleet]:
        statement = select(Fleet)
        if customer_id is not None:
            statement = statement.where(Fleet.customer_id == customer_id)
        if request_status is not None:
            statement = statement.where(Fleet.request_status == request_status)
        if is_active is not None:
            statement = statement.where(Fleet.is_active == is_active)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                or_(Fleet.code.ilike(pattern), Fleet.name.ilike(pattern))
            )
        return list(self.db.scalars(statement.order_by(Fleet.customer_id, Fleet.code)))

    def has_active_groups(self, fleet_id: int) -> bool:
        from app.models.commercial import FleetGroup

        return self.db.scalar(
            select(FleetGroup.id).where(
                FleetGroup.fleet_id == fleet_id, FleetGroup.is_active.is_(True)
            ).limit(1)
        ) is not None

    def create(self, values: dict[str, object]) -> Fleet:
        entity = Fleet(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Fleet, values: dict[str, object]) -> Fleet:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: Fleet) -> Fleet:
        entity.is_active = False
        self.db.flush()
        return entity
