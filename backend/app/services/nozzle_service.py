"""Business rules for pump nozzles."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.nozzle import Nozzle
from app.repositories.fuel_type_repository import FuelTypeRepository
from app.repositories.nozzle_repository import NozzleRepository
from app.repositories.pump_repository import PumpRepository
from app.repositories.tank_repository import TankRepository
from app.schemas.nozzle import NozzleCreate, NozzleUpdate


class NozzleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = NozzleRepository(db)
        self.pump_repository = PumpRepository(db)
        self.tank_repository = TankRepository(db)
        self.fuel_type_repository = FuelTypeRepository(db)

    def get(self, nozzle_id: int) -> Nozzle:
        entity = self.repository.get(nozzle_id)
        if entity is None:
            raise NotFoundError("Nozzle not found.")
        return entity

    def list(self) -> list[Nozzle]:
        return self.repository.list()

    def list_by_pump(self, pump_id: int) -> list[Nozzle]:
        self._get_pump(pump_id)
        return self.repository.get_by_pump(pump_id)

    def create(self, payload: NozzleCreate) -> Nozzle:
        values = payload.model_dump()
        self._validate_references(values["pump_id"], values["fuel_type_id"])
        self._validate_number_unique(values["pump_id"], values["nozzle_number"])
        return self._commit(lambda: self.repository.create(values))

    def update(self, nozzle_id: int, payload: NozzleUpdate) -> Nozzle:
        entity = self.get(nozzle_id)
        values = payload.model_dump(exclude_unset=True)
        pump_id = values.get("pump_id", entity.pump_id)
        fuel_type_id = values.get("fuel_type_id", entity.fuel_type_id)
        nozzle_number = values.get("nozzle_number", entity.nozzle_number)
        self._validate_references(pump_id, fuel_type_id)
        self._validate_number_unique(pump_id, nozzle_number, exclude_id=entity.id)
        totalizer = values.get("totalizer_liters")
        if totalizer is not None and totalizer < entity.totalizer_liters:
            raise BusinessRuleError("Nozzle totalizer cannot decrease.")
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, nozzle_id: int) -> Nozzle:
        return self._commit(lambda: self.repository.deactivate(self.get(nozzle_id)))

    def _get_pump(self, pump_id: int):
        pump = self.pump_repository.get(pump_id)
        if pump is None:
            raise NotFoundError("Pump not found.")
        return pump

    def _validate_references(self, pump_id: int, fuel_type_id: int) -> None:
        pump = self._get_pump(pump_id)
        tank = self.tank_repository.get(pump.tank_id)
        if tank is None:
            raise BusinessRuleError("Pump must be assigned to an existing tank.")
        fuel_type = self.fuel_type_repository.get(fuel_type_id)
        if fuel_type is None:
            raise NotFoundError("Fuel type not found.")
        if tank.fuel_type_id != fuel_type.id:
            raise BusinessRuleError("Nozzle fuel type must match the pump tank fuel type.")

    def _validate_number_unique(
        self, pump_id: int, nozzle_number: int, *, exclude_id: int | None = None
    ) -> None:
        existing = self.repository.get_by_pump_and_number(pump_id, nozzle_number)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("Nozzle number already exists for this pump.")

    def _commit(self, operation: object) -> Nozzle:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
