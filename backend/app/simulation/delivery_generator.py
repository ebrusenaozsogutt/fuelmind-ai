"""Deterministic, in-memory demo fuel delivery generation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from numbers import Real

from app.simulation.enums import SourceType
from app.simulation.random_source import RandomSource
from app.simulation.state import StationSimulationState, TankState

_EPSILON = 1e-9
_MINIMUM_AUTOMATIC_QUANTITY = 100.0


@dataclass(frozen=True)
class DeliveryResult:
    """Immutable outcome of one simulated delivery."""

    delivery_id: str
    station_id: int
    tank_id: int
    fuel_type_id: int
    delivery_timestamp: datetime
    requested_quantity_liters: float
    delivered_quantity_liters: float
    level_before_liters: float
    level_after_liters: float
    supplier_name: str | None
    source_type: SourceType
    is_automatic: bool
    was_clamped: bool


class DeliveryGenerator:
    """Create manual and automatic deliveries without persistence."""

    def __init__(self, *, random_source: RandomSource) -> None:
        """Use the simulation-owned deterministic random source."""

        self._random_source = random_source
        self._ids: dict[tuple[int, int, str], int] = {}

    def create_manual_delivery(
        self, *, tank: TankState, quantity_liters: float, delivery_timestamp: datetime,
        supplier_name: str | None = None,
    ) -> DeliveryResult:
        """Safely receive a requested manual quantity, clamped to capacity."""

        quantity = self._positive(quantity_liters, "quantity_liters")
        self._aware(delivery_timestamp)
        self._eligible_for_delivery(tank)
        return self._deliver(tank, quantity, delivery_timestamp, supplier_name, False)

    def should_create_automatic_delivery(
        self, *, tank: TankState, probability: float = 1.0
    ) -> bool:
        """Return whether an eligible low-stock tank receives an automatic delivery."""

        probability = self._probability(probability)
        if (
            not tank.is_active
            or tank.capacity_liters - tank.true_level_liters < _MINIMUM_AUTOMATIC_QUANTITY
            or tank.true_level_liters > tank.minimum_safe_level
        ):
            return False
        return self._random_source.chance(probability)

    def create_automatic_delivery(
        self, *, tank: TankState, delivery_timestamp: datetime,
        supplier_name: str | None = "Automatic Demo Supplier", probability: float = 1.0,
    ) -> DeliveryResult | None:
        """Create a deterministic 75–90% target-fill delivery when appropriate."""

        self._aware(delivery_timestamp)
        if not self.should_create_automatic_delivery(tank=tank, probability=probability):
            return None
        target = tank.capacity_liters * self._random_source.uniform(0.75, 0.90)
        requested = target - tank.true_level_liters
        if requested < _MINIMUM_AUTOMATIC_QUANTITY:
            return None
        return self._deliver(tank, requested, delivery_timestamp, supplier_name, True)

    def create_automatic_deliveries(
        self, *, station_state: StationSimulationState, delivery_timestamp: datetime,
        probability: float = 1.0,
    ) -> list[DeliveryResult]:
        """Create deliveries for eligible station tanks in tank ID order."""

        return [result for tank in sorted(station_state.tanks.values(), key=lambda item: item.tank_id)
                if (result := self.create_automatic_delivery(tank=tank, delivery_timestamp=delivery_timestamp, probability=probability)) is not None]

    def _deliver(self, tank: TankState, requested: float, timestamp: datetime,
                 supplier: str | None, automatic: bool) -> DeliveryResult:
        before = tank.true_level_liters
        delivered = min(requested, tank.capacity_liters - before)
        if delivered <= _EPSILON:
            raise ValueError("Tank has no remaining capacity.")
        tank.receive(delivered)
        return DeliveryResult(
            delivery_id=self._next_id(tank, timestamp), station_id=tank.station_id,
            tank_id=tank.tank_id, fuel_type_id=tank.fuel_type_id,
            delivery_timestamp=timestamp, requested_quantity_liters=requested,
            delivered_quantity_liters=delivered, level_before_liters=before,
            level_after_liters=tank.true_level_liters,
            supplier_name=(supplier.strip() or None) if isinstance(supplier, str) else None,
            source_type=SourceType.SIMULATION, is_automatic=automatic,
            was_clamped=delivered < requested,
        )

    def _next_id(self, tank: TankState, timestamp: datetime) -> str:
        stamp = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        key = (tank.station_id, tank.tank_id, stamp)
        self._ids[key] = self._ids.get(key, 0) + 1
        return f"DEL-{tank.station_id}-{tank.tank_id}-{stamp}-{self._ids[key]:03d}"

    @staticmethod
    def _aware(value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("delivery_timestamp must include a timezone.")

    @staticmethod
    def _eligible_for_delivery(tank: TankState) -> None:
        if not tank.is_active:
            raise ValueError("Inactive tank cannot receive a delivery.")
        if tank.capacity_liters - tank.true_level_liters <= _EPSILON:
            raise ValueError("Tank has no remaining capacity.")

    @staticmethod
    def _positive(value: Real, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) or value <= 0:
            raise ValueError(f"{field} must be a finite value greater than zero.")
        return float(value)

    @staticmethod
    def _probability(value: Real) -> float:
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) or not 0 <= value <= 1:
            raise ValueError("probability must be a finite value between 0 and 1.")
        return float(value)
