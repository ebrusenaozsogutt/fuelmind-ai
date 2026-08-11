"""Bounded scenario modifiers applied after normal tick generation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from app.simulation.state import PumpState, StationSimulationState, TankState
from app.utils.enums import ScenarioType, SimulationTargetType

ScenarioLoader = Callable[[datetime], list[object]]


class ScenarioEngine:
    """Apply active scenarios in demand, equipment, sensor, bounds order."""

    def __init__(self, loader: ScenarioLoader | None = None) -> None:
        self._loader = loader or (lambda _: [])
        self._stuck_levels: dict[tuple[int, int], float] = {}

    def active(self, moment: datetime) -> list[object]:
        return self._loader(moment)

    def demand_multiplier(self, scenarios: list[object]) -> float:
        return 1.8 if any(self._type(x) == ScenarioType.DEMAND_SURGE for x in scenarios) else 1.0

    def apply_equipment(self, state: StationSimulationState, scenarios: list[object], elapsed: float) -> None:
        for scenario in scenarios:
            kind = self._type(scenario)
            for pump in self._pumps(state, scenario):
                if kind == ScenarioType.FLOW_DROP:
                    pump.flow_rate *= 0.55
                    pump.motor_current = min(pump.maximum_motor_current, pump.motor_current * 1.18)
                    pump.pressure *= 0.82
                elif kind == ScenarioType.HIGH_MOTOR_CURRENT:
                    pump.motor_current = min(pump.maximum_motor_current, pump.motor_current * 1.35)
                    pump.temperature += 0.03 * elapsed
                    if elapsed >= 60:
                        pump.increment_error_count()

    def apply_sensor_and_physical(self, state: StationSimulationState, scenarios: list[object], elapsed: float) -> None:
        for scenario in scenarios:
            kind = self._type(scenario)
            for tank in self._tanks(state, scenario):
                if kind == ScenarioType.TANK_LEAK:
                    tank.withdraw(min(tank.available_liters, 0.01 * elapsed)) if tank.available_liters else None
                    tank.update_measured_level(tank.true_level_liters)
                elif kind == ScenarioType.SENSOR_STUCK:
                    # Keep the first normal reading seen during the scenario, not the true level.
                    key = (getattr(scenario, "id"), tank.tank_id)
                    frozen = self._stuck_levels.setdefault(key, tank.measured_level_liters)
                    tank.update_measured_level(float(frozen))
                elif kind == ScenarioType.SENSOR_SPIKE:
                    spike = max(5.0, tank.capacity_liters * 0.08)
                    tank.update_measured_level(min(tank.capacity_liters, tank.true_level_liters + spike))
                elif kind == ScenarioType.WATER_LEVEL_RISE:
                    tank.water_level += 0.002 * elapsed
        for tank in state.tanks.values():
            tank.true_level_liters = min(tank.capacity_liters, max(0.0, tank.true_level_liters))
            tank.measured_level_liters = min(tank.capacity_liters, max(0.0, tank.measured_level_liters))

    def public(self, scenarios: list[object]) -> list[dict[str, object]]:
        return [{"id": x.id, "name": x.name, "scenario_type": self._type(x).value,
                 "target_type": x.target_type.value, "target_id": x.target_id} for x in scenarios]

    @staticmethod
    def _type(scenario: object) -> ScenarioType:
        return ScenarioType(getattr(scenario, "scenario_type"))

    def _pumps(self, state: StationSimulationState, scenario: object) -> list[PumpState]:
        target = getattr(scenario, "target_type")
        return ([state.get_pump(getattr(scenario, "target_id"))] if target == SimulationTargetType.PUMP
                else list(state.pumps.values()) if target == SimulationTargetType.STATION else [])

    def _tanks(self, state: StationSimulationState, scenario: object) -> list[TankState]:
        target = getattr(scenario, "target_type")
        return ([state.get_tank(getattr(scenario, "target_id"))] if target == SimulationTargetType.TANK
                else list(state.tanks.values()) if target == SimulationTargetType.STATION else [])
