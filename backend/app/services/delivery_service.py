"""Transactional business rules for deliveries."""

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.delivery import Delivery
from app.repositories.delivery_repository import DeliveryRepository
from app.repositories.tank_repository import TankRepository
from app.schemas.delivery import DeliveryCreate


class DeliveryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DeliveryRepository(db)
        self.tank_repository = TankRepository(db)

    def get(self, delivery_id: int) -> Delivery:
        entity = self.repository.get(delivery_id)
        if entity is None:
            raise NotFoundError("Delivery not found.")
        return entity

    def list(self) -> list[Delivery]:
        return self.repository.list()

    def create(self, payload: DeliveryCreate) -> Delivery:
        """Create a delivery and increment its tank in one database transaction."""
        try:
            tank = self.tank_repository.get_for_update(payload.tank_id)
            if tank is None:
                raise NotFoundError("Tank not found.")
            if not tank.is_active:
                raise BusinessRuleError("Tank is inactive.")
            level_before = tank.current_level_liters
            level_after = level_before + payload.quantity_liters
            if level_after > tank.capacity_liters:
                raise BusinessRuleError("Delivery would exceed tank capacity.")

            values = payload.model_dump(exclude={"level_before", "level_after"})
            values.update(level_before=level_before, level_after=level_after)
            tank.current_level_liters = level_after
            entity = self.repository.create(values)
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
