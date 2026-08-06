"""Business rules for tanks."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.tank import Tank
from app.repositories.fuel_type_repository import FuelTypeRepository
from app.repositories.station_repository import StationRepository
from app.repositories.tank_repository import TankRepository
from app.schemas.tank import TankCreate, TankUpdate


class TankService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TankRepository(db)
        self.station_repository = StationRepository(db)
        self.fuel_type_repository = FuelTypeRepository(db)

    def get(self, tank_id: int) -> Tank:
        entity = self.repository.get(tank_id)
        if entity is None:
            raise NotFoundError("Tank not found.")
        return entity

    def list(self) -> list[Tank]:
        return self.repository.list()

    def create(self, payload: TankCreate) -> Tank:
        values = payload.model_dump()
        self._validate_references(values["station_id"], values["fuel_type_id"])
        self._validate_levels(values)
        if self.repository.get_by_station_and_code(
            values["station_id"], values["code"]
        ):
            raise ConflictError("Tank code already exists at this station.")
        return self._commit(lambda: self.repository.create(values))

    def update(self, tank_id: int, payload: TankUpdate) -> Tank:
        entity = self.get(tank_id)
        values = payload.model_dump(exclude_unset=True)
        station_id = values.get("station_id", entity.station_id)
        fuel_type_id = values.get("fuel_type_id", entity.fuel_type_id)
        self._validate_references(station_id, fuel_type_id)
        proposed = {
            "capacity_liters": values.get("capacity_liters", entity.capacity_liters),
            "current_level_liters": values.get(
                "current_level_liters", entity.current_level_liters
            ),
            "minimum_safe_level": values.get(
                "minimum_safe_level", entity.minimum_safe_level
            ),
            "critical_level": values.get("critical_level", entity.critical_level),
        }
        self._validate_levels(proposed)
        code = values.get("code", entity.code)
        existing = self.repository.get_by_station_and_code(station_id, code)
        if existing is not None and existing.id != entity.id:
            raise ConflictError("Tank code already exists at this station.")
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, tank_id: int) -> Tank:
        """Soft-delete a tank so its operational history remains intact."""
        entity = self.get(tank_id)
        return self._commit(lambda: self.repository.deactivate(entity))

    def _validate_references(self, station_id: int, fuel_type_id: int) -> None:
        if self.station_repository.get(station_id) is None:
            raise NotFoundError("Station not found.")
        fuel_type = self.fuel_type_repository.get(fuel_type_id)
        if fuel_type is None:
            raise NotFoundError("Fuel type not found.")
        if not fuel_type.is_active:
            raise BusinessRuleError("Tank fuel type must be active.")

    @staticmethod
    def _validate_levels(values: dict[str, Decimal]) -> None:
        capacity = values["capacity_liters"]
        for field in ("current_level_liters", "minimum_safe_level", "critical_level"):
            if values[field] > capacity:
                raise BusinessRuleError(f"{field} cannot exceed tank capacity.")

    def _commit(self, operation: object) -> Tank:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
