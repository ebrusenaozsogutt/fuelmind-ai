"""Business rules for pumps."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.pump import Pump
from app.repositories.pump_repository import PumpRepository
from app.repositories.station_repository import StationRepository
from app.repositories.tank_repository import TankRepository
from app.schemas.pump import PumpCreate, PumpUpdate


class PumpService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PumpRepository(db)
        self.station_repository = StationRepository(db)
        self.tank_repository = TankRepository(db)

    def get(self, pump_id: int) -> Pump:
        entity = self.repository.get(pump_id)
        if entity is None:
            raise NotFoundError("Pump not found.")
        return entity

    def list(self) -> list[Pump]:
        return self.repository.list()

    def create(self, payload: PumpCreate) -> Pump:
        values = payload.model_dump()
        self._validate_relationship(values["station_id"], values["tank_id"])
        self._validate_flow_rates(
            values["minimum_flow_rate"], values["nominal_flow_rate"]
        )
        if self.repository.get_by_station_and_code(
            values["station_id"], values["code"]
        ):
            raise ConflictError("Pump code already exists at this station.")
        return self._commit(lambda: self.repository.create(values))

    def update(self, pump_id: int, payload: PumpUpdate) -> Pump:
        entity = self.get(pump_id)
        values = payload.model_dump(exclude_unset=True)
        station_id = values.get("station_id", entity.station_id)
        tank_id = values.get("tank_id", entity.tank_id)
        self._validate_relationship(station_id, tank_id)
        self._validate_flow_rates(
            values.get("minimum_flow_rate", entity.minimum_flow_rate),
            values.get("nominal_flow_rate", entity.nominal_flow_rate),
        )
        code = values.get("code", entity.code)
        existing = self.repository.get_by_station_and_code(station_id, code)
        if existing is not None and existing.id != entity.id:
            raise ConflictError("Pump code already exists at this station.")
        return self._commit(lambda: self.repository.update(entity, values))

    def deactivate(self, pump_id: int) -> Pump:
        entity = self.get(pump_id)
        return self._commit(lambda: self.repository.deactivate(entity))

    def _validate_relationship(self, station_id: int, tank_id: int) -> None:
        if self.station_repository.get(station_id) is None:
            raise NotFoundError("Station not found.")
        tank = self.tank_repository.get(tank_id)
        if tank is None:
            raise NotFoundError("Tank not found.")
        if tank.station_id != station_id:
            raise BusinessRuleError("Pump and tank must belong to the same station.")

    @staticmethod
    def _validate_flow_rates(minimum: Decimal, nominal: Decimal) -> None:
        if minimum > nominal:
            raise BusinessRuleError(
                "Minimum flow rate cannot exceed nominal flow rate."
            )

    def _commit(self, operation: object) -> Pump:
        try:
            entity = operation()  # type: ignore[operator]
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
