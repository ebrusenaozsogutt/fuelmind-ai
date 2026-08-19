"""Database queries for fleet groups."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commercial import FleetGroup, Vehicle


class FleetGroupRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, group_id: int) -> FleetGroup | None:
        return self.db.get(FleetGroup, group_id)

    def get_by_fleet_and_code(self, fleet_id: int, code: str) -> FleetGroup | None:
        return self.db.scalar(
            select(FleetGroup).where(
                FleetGroup.fleet_id == fleet_id, FleetGroup.code == code
            )
        )

    def list(
        self, *, fleet_id: int | None = None, is_active: bool | None = None
    ) -> list[FleetGroup]:
        statement = select(FleetGroup)
        if fleet_id is not None:
            statement = statement.where(FleetGroup.fleet_id == fleet_id)
        if is_active is not None:
            statement = statement.where(FleetGroup.is_active == is_active)
        return list(self.db.scalars(statement.order_by(FleetGroup.fleet_id, FleetGroup.code)))

    def has_active_vehicles(self, group_id: int) -> bool:
        return self.db.scalar(
            select(Vehicle.id).where(
                Vehicle.fleet_group_id == group_id, Vehicle.is_active.is_(True)
            ).limit(1)
        ) is not None

    def create(self, values: dict[str, object]) -> FleetGroup:
        entity = FleetGroup(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: FleetGroup, values: dict[str, object]) -> FleetGroup:
        for field, value in values.items():
            setattr(entity, field, value)
        self.db.flush()
        return entity

    def deactivate(self, entity: FleetGroup) -> FleetGroup:
        entity.is_active = False
        self.db.flush()
        return entity
