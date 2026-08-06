"""Database queries for sales."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sale import Sale


class SaleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, sale_id: int) -> Sale | None:
        return self.db.get(Sale, sale_id)

    def list(self) -> list[Sale]:
        return list(self.db.scalars(select(Sale).order_by(Sale.sale_timestamp.desc())))

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
