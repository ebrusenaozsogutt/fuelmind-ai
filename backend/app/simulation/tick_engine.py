"""Orchestrate one deterministic simulation tick."""

from math import isfinite
from numbers import Real

from app.simulation.clock import SimulationClock
from app.simulation.config import SimulationConfig
from app.simulation.delivery_generator import DeliveryGenerator
from app.simulation.pump_generator import PumpGenerator
from app.simulation.sales_generator import SalesGenerator
from app.simulation.state import StationSimulationState
from app.simulation.tank_generator import TankGenerator
from app.simulation.tick_result import SimulationTickEvent, SimulationTickResult
from app.simulation.validators import SimulationValidator


class TickEngine:
    """Coordinate existing generators for exactly one station tick."""

    def __init__(
        self,
        *,
        config: SimulationConfig,
        clock: SimulationClock,
        sales_generator: SalesGenerator,
        tank_generator: TankGenerator,
        pump_generator: PumpGenerator,
        delivery_generator: DeliveryGenerator,
        validator: SimulationValidator,
        fuel_codes_by_id: dict[int, str],
        unit_prices_by_fuel: dict[str, float],
        base_sale_probability: float = 0.3,
        automatic_delivery_probability: float = 0.0,
    ) -> None:
        (
            self.config,
            self.clock,
            self.sales_generator,
            self.tank_generator,
            self.pump_generator,
            self.delivery_generator,
            self.validator,
        ) = (
            config,
            clock,
            sales_generator,
            tank_generator,
            pump_generator,
            delivery_generator,
            validator,
        )
        self._prob(base_sale_probability, "base_sale_probability")
        self._prob(automatic_delivery_probability, "automatic_delivery_probability")
        if not fuel_codes_by_id:
            raise ValueError("fuel_codes_by_id cannot be empty.")
        self.fuel_codes_by_id = dict(fuel_codes_by_id)
        self.unit_prices_by_fuel = dict(unit_prices_by_fuel)
        self.base_sale_probability = base_sale_probability
        self.automatic_delivery_probability = automatic_delivery_probability
        for key, code in self.fuel_codes_by_id.items():
            if key <= 0 or not code.strip() or code not in self.unit_prices_by_fuel:
                raise ValueError("Fuel mapping or price is invalid.")
        for price in self.unit_prices_by_fuel.values():
            if (
                isinstance(price, bool)
                or not isinstance(price, Real)
                or not isfinite(price)
                or price < 0
            ):
                raise ValueError("Unit price is invalid.")

    def run_tick(self, station_state: StationSimulationState) -> SimulationTickResult:
        """Run the prescribed single-tick generator order."""
        if self.clock.is_paused:
            raise ValueError("Cannot run a tick while clock is paused.")
        self.validator.validate_station_state(station_state)
        now = self.clock.advance()
        sequence = station_state.next_sequence()
        elapsed = self.config.simulation_step_seconds * self.clock.speed_multiplier
        events = []
        for pump_id in sorted(station_state.pumps):
            pump = station_state.pumps[pump_id]
            code = self.fuel_codes_by_id.get(pump.fuel_type_id)
            if code is None:
                raise ValueError(f"Missing fuel code for {pump.fuel_type_id}.")
            sale = self.sales_generator.try_start_sale(
                station_state=station_state,
                pump_id=pump_id,
                moment=now,
                base_probability=self.base_sale_probability,
                fuel_code=code,
                unit_price=self.unit_prices_by_fuel[code],
            )
            if sale:
                events.append(
                    SimulationTickEvent(
                        "SALE_STARTED",
                        station_state.station_id,
                        now,
                        "PUMP",
                        pump_id,
                        {"sale_id": sale.sale_id},
                    )
                )
        sales = self.sales_generator.advance_all_sales(
            station_state=station_state, elapsed_seconds=elapsed, updated_at=now
        )
        completed = [x.completed_sale for x in sales if x.completed_sale]
        for sale in completed:
            events.append(
                SimulationTickEvent(
                    "SALE_COMPLETED",
                    station_state.station_id,
                    now,
                    "PUMP",
                    sale.pump_id,
                    {"sale_id": sale.sale_id},
                )
            )
        deliveries = self.delivery_generator.create_automatic_deliveries(
            station_state=station_state,
            delivery_timestamp=now,
            probability=self.automatic_delivery_probability,
        )
        for item in deliveries:
            events.append(
                SimulationTickEvent(
                    "DELIVERY_COMPLETED",
                    station_state.station_id,
                    now,
                    "TANK",
                    item.tank_id,
                    {"delivery_id": item.delivery_id},
                )
            )
        tanks = self.tank_generator.update_tanks(
            tanks=[station_state.tanks[x] for x in sorted(station_state.tanks)],
            elapsed_seconds=elapsed,
        )
        pumps = self.pump_generator.update_pumps(
            pumps=[station_state.pumps[x] for x in sorted(station_state.pumps)],
            elapsed_seconds=elapsed,
        )
        result = SimulationTickResult(
            station_state.station_id,
            now,
            sequence,
            tanks,
            pumps,
            sales,
            completed,
            deliveries,
            events,
        )
        self.validator.validate_tick_result(result, station_state)
        self.validator.validate_station_state(station_state)
        return result

    @staticmethod
    def _prob(value: Real, name: str) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not isfinite(value)
            or not 0 <= value <= 1
        ):
            raise ValueError(f"{name} must be between 0 and 1.")
