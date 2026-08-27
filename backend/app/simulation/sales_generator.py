"""Deterministic, in-memory sale lifecycle generation for simulations."""
#akaryakıt istasyonlarında satışların simülasyonunu yapmak için kullanılan, bellek içi satış yaşam döngüsü üretimi.
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from math import isfinite
from numbers import Real
from types import MappingProxyType

from app.simulation.demand_profile import DemandProfile
from app.simulation.random_source import RandomSource
from app.simulation.state import ActiveSaleState, StationSimulationState
from app.services.commercial_sale_service import CommercialSaleSelection

_EPSILON = 1e-9
_MINIMUM_START_QUANTITY_LITERS = 1.0


@dataclass(frozen=True)
class _SaleQuantityProfile:
    """Immutable random quantity bounds for one canonical fuel type."""

    mean: float
    standard_deviation: float
    minimum: float
    maximum: float


@dataclass(frozen=True)
class SaleAdvanceResult:
    """Describe one active sale's progress during a simulation tick."""

    pump_id: int
    sale_id: str
    dispensed_quantity_liters: float
    completed_sale: ActiveSaleState | None


class SalesGenerator:
    """Start and advance deterministic in-memory fuel sales."""

    _FUEL_ALIASES = MappingProxyType(
        {
            "DIESEL": "DIESEL",
            "MOTORIN": "DIESEL",
            "MOTOR\u0130N": "DIESEL",
            "GASOLINE": "GASOLINE",
            "BENZIN": "GASOLINE",
            "BENZ\u0130N": "GASOLINE",
            "LPG": "LPG",
        }
    )
    _QUANTITY_PROFILES = MappingProxyType(
        {
            "DIESEL": _SaleQuantityProfile(45.0, 20.0, 5.0, 120.0),
            "GASOLINE": _SaleQuantityProfile(30.0, 13.0, 5.0, 90.0),
            "LPG": _SaleQuantityProfile(24.0, 10.0, 5.0, 70.0),
        }
    )

    def __init__(
        self,
        *,
        random_source: RandomSource,
        demand_profile: DemandProfile,
        commercial_selector: object | None = None,
        operations_selector: object | None = None,
    ) -> None:
        """Use supplied deterministic random and demand dependencies."""

        self._random_source = random_source
        self._demand_profile = demand_profile
        self._commercial_selector = commercial_selector
        self._operations_selector = operations_selector
        self._sale_counters: dict[int, int] = {}

    def try_start_sale(
        self,
        *,
        station_state: StationSimulationState,
        pump_id: int,
        moment: datetime,
        base_probability: float,
        fuel_code: str,
        unit_price: float,
        scenario_multiplier: float = 1.0,
    ) -> ActiveSaleState | None:
        """Start a compatible idle-pump sale when its demand chance succeeds."""

        self._require_aware(moment, "moment")
        self._validate_non_negative(unit_price, "unit_price")
        canonical_fuel_code = self._canonical_fuel_code(fuel_code)
        probability = self._demand_profile.calculate_sale_probability(
            base_probability,
            moment,
            fuel_code,
            scenario_multiplier,
        )
        pump = station_state.get_pump(pump_id)
        tank = station_state.get_tank(pump.tank_id)

        if (
            not pump.is_active
            or not pump.is_idle
            or station_state.has_active_sale(pump_id)
            or not tank.is_active
            or tank.available_liters < _MINIMUM_START_QUANTITY_LITERS
            or pump.station_id != station_state.station_id
            or tank.station_id != station_state.station_id
            or pump.fuel_type_id != tank.fuel_type_id
        ):
            return None
        if not self._random_source.chance(probability):
            return None

        target_quantity_liters = min(
            self._next_quantity_liters(canonical_fuel_code), tank.available_liters
        )
        if target_quantity_liters < _MINIMUM_START_QUANTITY_LITERS:
            return None

        nozzle_id = self._select_nozzle_id(station_state, pump_id)
        commercial_snapshot = None
        if self._commercial_selector is not None and nozzle_id is not None:
            selection: CommercialSaleSelection = self._commercial_selector(
                station_id=station_state.station_id,
                fuel_type_id=tank.fuel_type_id,
                quantity_liters=Decimal(str(target_quantity_liters)),
                started_at=moment,
                random_source=self._random_source,
            )
            if selection.configured and selection.snapshot is None:
                return None
            commercial_snapshot = selection.snapshot

        operations_selection = None
        if self._operations_selector is not None:
            operations_selection = self._operations_selector(
                station_id=station_state.station_id,
                simulation_time=moment,
                random_source=self._random_source,
            )

        sale = ActiveSaleState(
            sale_id=self._next_sale_id(station_state.station_id, pump_id),
            station_id=station_state.station_id,
            tank_id=tank.tank_id,
            pump_id=pump.pump_id,
            fuel_type_id=tank.fuel_type_id,
            started_at=moment,
            target_quantity_liters=target_quantity_liters,
            dispensed_quantity_liters=0.0,
            unit_price=unit_price,
            nozzle_id=nozzle_id,
            commercial_snapshot=commercial_snapshot,
            attendant_id=(
                operations_selection.attendant_id
                if operations_selection is not None
                else None
            ),
            attendant_name=(
                operations_selection.attendant_name
                if operations_selection is not None
                else None
            ),
            shift_id=(
                operations_selection.shift_id
                if operations_selection is not None
                else None
            ),
            shift_name=(
                operations_selection.shift_name
                if operations_selection is not None
                else None
            ),
        )
        station_state.start_sale(sale)
        try:
            pump.start_dispensing()
            if pump.flow_rate <= 0:
                # A later pump sensor generator will replace this initial value each tick.
                pump.flow_rate = pump.nominal_flow_rate
        except Exception:
            station_state.complete_sale(pump_id)
            raise
        return sale

    def _select_nozzle_id(
        self, station_state: StationSimulationState, pump_id: int
    ) -> int | None:
        """Choose an available persisted nozzle without changing legacy sales."""

        nozzles = station_state.available_nozzles(pump_id)
        if not nozzles:
            return None
        return self._random_source.choice(sorted(nozzle.nozzle_id for nozzle in nozzles))

    def advance_active_sale(
        self,
        *,
        station_state: StationSimulationState,
        pump_id: int,
        elapsed_seconds: float,
        updated_at: datetime,
    ) -> SaleAdvanceResult:
        """Advance a pump sale and return the dispensed quantity and completion."""

        elapsed_seconds = self._validate_positive(elapsed_seconds, "elapsed_seconds")
        self._require_aware(updated_at, "updated_at")
        sale = station_state.get_active_sale(pump_id)
        pump = station_state.get_pump(pump_id)
        tank = station_state.get_tank(sale.tank_id)
        if not pump.is_active_status:
            raise ValueError("Pump must be active while advancing a sale.")
        if pump.flow_rate <= 0:
            raise ValueError("Pump flow_rate must be greater than zero.")
        if updated_at < sale.last_updated_at:
            raise ValueError("updated_at cannot precede the active sale timeline.")

        requested_quantity = pump.flow_rate * elapsed_seconds / 60.0
        actual_quantity = min(
            requested_quantity,
            sale.remaining_quantity_liters,
            tank.available_liters,
        )
        if actual_quantity > _EPSILON:
            dispensed_quantity = sale.dispense(actual_quantity, updated_at)
            tank.withdraw(dispensed_quantity)
        else:
            dispensed_quantity = 0.0
        pump.increment_working_time(elapsed_seconds)

        completed_sale = None
        if sale.is_completed or tank.available_liters < _EPSILON:
            finished_sale = station_state.complete_sale(pump_id)
            pump.stop_dispensing()
            # Multiple pumps may share one tank.  A preceding pump can empty it
            # within this same tick, leaving a later active sale with no physical
            # fuel to dispense.  End that in-memory attempt, but it is not a
            # completed sale and must never reach the completed-sale persistence
            # pipeline (which represents only positive physical deliveries).
            if finished_sale.dispensed_quantity_liters > _EPSILON:
                completed_sale = finished_sale
        return SaleAdvanceResult(
            pump_id=pump_id,
            sale_id=sale.sale_id,
            dispensed_quantity_liters=dispensed_quantity,
            completed_sale=completed_sale,
        )

    def advance_all_sales(
        self,
        *,
        station_state: StationSimulationState,
        elapsed_seconds: float,
        updated_at: datetime,
    ) -> list[SaleAdvanceResult]:
        """Advance a stable snapshot of every active sale at a station."""

        return [
            self.advance_active_sale(
                station_state=station_state,
                pump_id=pump_id,
                elapsed_seconds=elapsed_seconds,
                updated_at=updated_at,
            )
            for pump_id in list(station_state.active_sales)
        ]

    def _next_quantity_liters(self, canonical_fuel_code: str) -> float:
        profile = self._QUANTITY_PROFILES[canonical_fuel_code]
        return self._random_source.clamped_normal(
            profile.mean,
            profile.standard_deviation,
            profile.minimum,
            profile.maximum,
        )

    def _next_sale_id(self, station_id: int, pump_id: int) -> str:
        counter = self._sale_counters.get(station_id, 0) + 1
        self._sale_counters[station_id] = counter
        return f"SIM-{station_id}-{pump_id}-{counter:06d}"

    def _canonical_fuel_code(self, fuel_code: str) -> str:
        # DemandProfile remains the source of truth for supported codes and validation.
        self._demand_profile.get_fuel_multiplier(fuel_code)
        normalized = fuel_code.strip().upper()
        try:
            return self._FUEL_ALIASES[normalized]
        except KeyError as exc:
            raise ValueError(f"Unsupported fuel code: {fuel_code!r}.") from exc

    @staticmethod
    def _require_aware(value: datetime, field_name: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must include a timezone.")
        return value

    @staticmethod
    def _validate_positive(value: Real, field_name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
            raise ValueError(f"{field_name} must be a finite numeric value.")
        if value <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return float(value)

    @staticmethod
    def _validate_non_negative(value: Real, field_name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
            raise ValueError(f"{field_name} must be a finite numeric value.")
        if value < 0:
            raise ValueError(f"{field_name} cannot be negative.")
        return float(value)
