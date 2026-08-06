"""Pure validation for simulation runtime state and tick results."""

from math import isfinite
from numbers import Real
from app.simulation.state import (
    ActiveSaleState,
    PumpState,
    StationSimulationState,
    TankState,
)
from app.simulation.tick_result import SimulationTickResult
from app.utils.enums import PumpStatus


class SimulationValidator:
    """Validate mutable simulation objects without changing them."""

    @staticmethod
    def _number(value: Real, name: str, minimum: float | None = None) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not isfinite(value)
            or (minimum is not None and value < minimum)
        ):
            raise ValueError(f"{name} must be a finite number.")

    def validate_tank_state(self, tank: TankState) -> None:
        for n in ("tank_id", "station_id", "fuel_type_id"):
            if getattr(tank, n) <= 0:
                raise ValueError(f"tank.{n} must be positive.")
        if not tank.code.strip():
            raise ValueError("tank.code cannot be empty.")
        for n in (
            "capacity_liters",
            "true_level_liters",
            "measured_level_liters",
            "minimum_safe_level",
            "critical_level",
            "water_level",
        ):
            self._number(getattr(tank, n), f"tank.{n}", 0)
        self._number(tank.temperature, "tank.temperature")
        if (
            tank.capacity_liters <= 0
            or max(tank.true_level_liters, tank.measured_level_liters)
            > tank.capacity_liters
        ):
            raise ValueError("Tank level cannot exceed capacity.")

    def validate_pump_state(self, pump: PumpState) -> None:
        if not isinstance(pump.status, PumpStatus):
            raise ValueError("pump.status is invalid.")
        for n in ("pump_id", "station_id", "tank_id", "fuel_type_id"):
            if getattr(pump, n) <= 0:
                raise ValueError(f"pump.{n} must be positive.")
        for n in (
            "nominal_flow_rate",
            "minimum_flow_rate",
            "maximum_motor_current",
            "maximum_pressure",
            "flow_rate",
            "pressure",
            "motor_current",
            "total_working_hours",
        ):
            self._number(getattr(pump, n), f"pump.{n}", 0)
        self._number(pump.temperature, "pump.temperature")
        if pump.status == PumpStatus.OFFLINE and any(
            (pump.flow_rate, pump.pressure, pump.motor_current)
        ):
            raise ValueError("Offline pump has active sensors.")

    def validate_active_sale(self, sale: ActiveSaleState) -> None:
        for n in ("target_quantity_liters", "dispensed_quantity_liters", "unit_price"):
            self._number(getattr(sale, n), f"sale.{n}", 0)
        if (
            sale.target_quantity_liters <= 0
            or sale.dispensed_quantity_liters > sale.target_quantity_liters
        ):
            raise ValueError("Invalid sale quantities.")
        if (
            sale.started_at.tzinfo is None
            or sale.last_updated_at.tzinfo is None
            or sale.last_updated_at < sale.started_at
        ):
            raise ValueError("Invalid sale timestamps.")

    def validate_station_state(self, state: StationSimulationState) -> None:
        if state.station_id <= 0 or state.sequence_number < 0:
            raise ValueError("Invalid station state.")
        for tank in state.tanks.values():
            self.validate_tank_state(tank)
        for pump in state.pumps.values():
            self.validate_pump_state(pump)
            if pump.station_id != state.station_id or pump.tank_id not in state.tanks:
                raise ValueError("Pump references invalid tank.")
            if pump.fuel_type_id != state.tanks[pump.tank_id].fuel_type_id:
                raise ValueError("Pump fuel type does not match tank.")
        sale_ids: set[str] = set()
        for pump_id, sale in state.active_sales.items():
            self.validate_active_sale(sale)
            if pump_id != sale.pump_id or pump_id not in state.pumps:
                raise ValueError("Active sale references invalid pump.")
            if sale.sale_id in sale_ids or sale.is_completed:
                raise ValueError("Duplicate or completed active sale.")
            sale_ids.add(sale.sale_id)
            pump = state.pumps[pump_id]
            if pump.status != PumpStatus.ACTIVE or sale.tank_id != pump.tank_id:
                raise ValueError("Active sale is incompatible with pump.")

    def validate_tick_result(
        self,
        result: SimulationTickResult,
        station_state: StationSimulationState | None = None,
    ) -> None:
        if (
            result.station_id <= 0
            or result.sequence_number <= 0
            or result.simulation_time.tzinfo is None
        ):
            raise ValueError("Invalid tick result.")
        if len({x.tank_id for x in result.tank_results}) != len(result.tank_results):
            raise ValueError("Duplicate tank result.")
        if len({x.pump_id for x in result.pump_results}) != len(result.pump_results):
            raise ValueError("Duplicate pump result.")
        if len({x.delivery_id for x in result.deliveries}) != len(result.deliveries):
            raise ValueError("Duplicate delivery result.")
        for tank in result.tank_results:
            self.validate_tank_state(tank)
            if tank.station_id != result.station_id:
                raise ValueError("Tank result station mismatch.")
        for pump in result.pump_results:
            self.validate_pump_state(pump)
            if pump.station_id != result.station_id:
                raise ValueError("Pump result station mismatch.")
        for delivery in result.deliveries:
            if (
                delivery.station_id != result.station_id
                or abs(
                    (delivery.level_after_liters - delivery.level_before_liters)
                    - delivery.delivered_quantity_liters
                )
                > 1e-9
            ):
                raise ValueError("Invalid delivery result.")
        for event in result.events:
            if event.station_id != result.station_id:
                raise ValueError("Event station mismatch.")
        if station_state and result.station_id != station_state.station_id:
            raise ValueError("Tick station mismatch.")
        if station_state:
            for tank in result.tank_results:
                if tank.tank_id not in station_state.tanks:
                    raise ValueError("Tank result is not in station state.")
            for pump in result.pump_results:
                if pump.pump_id not in station_state.pumps:
                    raise ValueError("Pump result is not in station state.")
