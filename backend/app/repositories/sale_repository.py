"""Database queries for sales."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sale import Sale


class SaleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, sale_id: int) -> Sale | None:
        return self.db.get(Sale, sale_id)

    def list(
        self,
        *,
        customer_id: int | None = None,
        vehicle_id: int | None = None,
        fuel_card_id: int | None = None,
    ) -> list[Sale]:
        statement = select(Sale)
        if customer_id is not None:
            statement = statement.where(Sale.customer_id == customer_id)
        if vehicle_id is not None:
            statement = statement.where(Sale.vehicle_id == vehicle_id)
        if fuel_card_id is not None:
            statement = statement.where(Sale.fuel_card_id == fuel_card_id)
        # ``created_at`` is the durable completion order.  It prevents old, accidentally
        # future-dated legacy rows from hiding newly completed realtime commercial sales.
        return list(self.db.scalars(statement.order_by(Sale.created_at.desc(), Sale.id.desc())))

    def create(self, values: dict[str, object]) -> Sale:
        entity = Sale(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Sale, values: dict[str, object]) -> Sale:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity
