"""Database queries for deliveries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery import Delivery


class DeliveryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, delivery_id: int) -> Delivery | None:
        return self.db.get(Delivery, delivery_id)

    def list(self) -> list[Delivery]:
        return list(
            self.db.scalars(
                select(Delivery).order_by(Delivery.delivery_timestamp.desc())
            )
        )

    def create(self, values: dict[str, object]) -> Delivery:
        entity = Delivery(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: Delivery, values: dict[str, object]) -> Delivery:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity
