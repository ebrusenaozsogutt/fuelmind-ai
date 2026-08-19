"""Database queries for station fuel-price history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.commercial import FuelPrice


class FuelPriceRepository:
    """Persist and resolve effective station fuel prices."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, fuel_price_id: int) -> FuelPrice | None:
        return self.db.get(FuelPrice, fuel_price_id)

    def list(
        self,
        *,
        station_id: int | None = None,
        fuel_type_id: int | None = None,
        is_active: bool | None = None,
    ) -> list[FuelPrice]:
        statement = select(FuelPrice)
        if station_id is not None:
            statement = statement.where(FuelPrice.station_id == station_id)
        if fuel_type_id is not None:
            statement = statement.where(FuelPrice.fuel_type_id == fuel_type_id)
        if is_active is not None:
            statement = statement.where(FuelPrice.is_active == is_active)
        return list(
            self.db.scalars(
                statement.order_by(FuelPrice.effective_from.desc(), FuelPrice.id.desc())
            )
        )

    def list_history(self, station_id: int, fuel_type_id: int) -> list[FuelPrice]:
        return self.list(station_id=station_id, fuel_type_id=fuel_type_id)

    def list_active_for_pair(self, station_id: int, fuel_type_id: int) -> list[FuelPrice]:
        statement = select(FuelPrice).where(
            FuelPrice.station_id == station_id,
            FuelPrice.fuel_type_id == fuel_type_id,
            FuelPrice.is_active.is_(True),
        )
        return list(self.db.scalars(statement.order_by(FuelPrice.effective_from)))

    def get_active_price(
        self, station_id: int, fuel_type_id: int, effective_at: datetime
    ) -> FuelPrice | None:
        statement = (
            select(FuelPrice)
            .where(
                FuelPrice.station_id == station_id,
                FuelPrice.fuel_type_id == fuel_type_id,
                FuelPrice.is_active.is_(True),
                FuelPrice.effective_from <= effective_at,
                or_(
                    FuelPrice.effective_until.is_(None),
                    FuelPrice.effective_until > effective_at,
                ),
            )
            .order_by(FuelPrice.effective_from.desc(), FuelPrice.id.desc())
        )
        return self.db.scalar(statement)

    def create(self, values: dict[str, object]) -> FuelPrice:
        entity = FuelPrice(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: FuelPrice, values: dict[str, object]) -> FuelPrice:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: FuelPrice) -> FuelPrice:
        entity.is_active = False
        self.db.flush()
        return entity
