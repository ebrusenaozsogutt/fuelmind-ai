"""Transactional business rules for sales."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.tank import Tank
from app.repositories.fuel_type_repository import FuelTypeRepository
from app.repositories.pump_repository import PumpRepository
from app.repositories.sale_repository import SaleRepository
from app.repositories.station_repository import StationRepository
from app.repositories.tank_repository import TankRepository
from app.schemas.sale import SaleCreate
from app.utils.enums import PumpStatus


class SaleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SaleRepository(db)
        self.station_repository = StationRepository(db)
        self.tank_repository = TankRepository(db)
        self.pump_repository = PumpRepository(db)
        self.fuel_type_repository = FuelTypeRepository(db)

    def get(self, sale_id: int) -> Sale:
        entity = self.repository.get(sale_id)
        if entity is None:
            raise NotFoundError("Sale not found.")
        return entity

    def list(self) -> list[Sale]:
        return self.repository.list()

    def create(self, payload: SaleCreate) -> Sale:
        """Create a sale and decrement its tank in one database transaction."""
        try:
            station = self.station_repository.get(payload.station_id)
            if station is None:
                raise NotFoundError("Station not found.")
            if not station.is_active:
                raise BusinessRuleError("Station is inactive.")
            tank = self.tank_repository.get_for_update(payload.tank_id)
            if tank is None:
                raise NotFoundError("Tank not found.")
            if not tank.is_active:
                raise BusinessRuleError("Tank is inactive.")
            pump = self.pump_repository.get(payload.pump_id)
            if pump is None:
                raise NotFoundError("Pump not found.")
            if not pump.is_active:
                raise BusinessRuleError("Pump is inactive.")
            if pump.status != PumpStatus.ACTIVE:
                raise BusinessRuleError("Pump must be ACTIVE to create a sale.")
            fuel_type = self.fuel_type_repository.get(payload.fuel_type_id)
            if fuel_type is None:
                raise NotFoundError("Fuel type not found.")
            if not fuel_type.is_active:
                raise BusinessRuleError("Fuel type is inactive.")
            self._validate_relationships(payload, tank, pump)
            if tank.current_level_liters < payload.quantity_liters:
                raise BusinessRuleError(
                    "Tank does not contain enough fuel for this sale."
                )

            level_before = tank.current_level_liters
            level_after = level_before - payload.quantity_liters
            total_amount = (payload.quantity_liters * payload.unit_price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            values = payload.model_dump(
                exclude={"total_amount", "level_before", "level_after"}
            )
            values.update(
                total_amount=total_amount,
                level_before=level_before,
                level_after=level_after,
            )
            tank.current_level_liters = level_after
            entity = self.repository.create(values)
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _validate_relationships(payload: SaleCreate, tank: Tank, pump: Pump) -> None:
        if (
            tank.station_id != payload.station_id
            or pump.station_id != payload.station_id
        ):
            raise BusinessRuleError(
                "Sale station must match the tank and pump station."
            )
        if pump.tank_id != tank.id:
            raise BusinessRuleError("Sale pump must be connected to the sale tank.")
        if tank.fuel_type_id != payload.fuel_type_id:
            raise BusinessRuleError("Sale fuel type must match the tank fuel type.")
