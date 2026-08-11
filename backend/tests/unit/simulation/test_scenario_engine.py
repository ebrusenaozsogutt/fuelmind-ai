"""Scenario scheduling and bounded modifier coverage."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.simulation import (
    DeliveryGenerator, DemandProfile, PumpGenerator, PumpState, RandomSource,
    SalesGenerator, ScenarioEngine, SimulationClock, SimulationConfig,
    SimulationValidator, StationSimulationState, TankGenerator, TankState, TickEngine,
)
from app.repositories.simulation_scenario_repository import SimulationScenarioRepository
from app.utils.enums import PumpStatus, ScenarioType, SimulationStatus, SimulationTargetType

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def scenario(kind: ScenarioType, *, start: datetime = START + timedelta(seconds=5), duration: int = 1):
    return SimpleNamespace(id=1, name=kind.value, scenario_type=kind,
        target_type=SimulationTargetType.STATION, target_id=1, start_time=start,
        duration_minutes=duration, parameters_json={}, status=SimulationStatus.CREATED)


def build(kind: ScenarioType | None = None, seed: int = 7, probability: float = 1.0):
    config = SimulationConfig(simulation_step_seconds=5, random_seed=seed)
    random = RandomSource(seed)
    state = StationSimulationState(1)
    state.add_tank(TankState(1, 1, 1, "T", 1000, 500, 500, 200, 100, 20, 0, "OK"))
    state.add_pump(PumpState(1, 1, 1, 1, "P", PumpStatus.IDLE, 42, 10, 20, 8))
    item = scenario(kind) if kind else None
    def loader(moment):
        if item is None or moment < item.start_time or moment >= item.start_time + timedelta(minutes=item.duration_minutes):
            return []
        item.status = SimulationStatus.RUNNING
        return [item]
    return TickEngine(config=config, clock=SimulationClock(config, START),
        sales_generator=SalesGenerator(random_source=random, demand_profile=DemandProfile()),
        tank_generator=TankGenerator(random_source=random), pump_generator=PumpGenerator(random_source=random),
        delivery_generator=DeliveryGenerator(random_source=random), validator=SimulationValidator(),
        fuel_codes_by_id={1: "DIESEL"}, unit_prices_by_fuel={"DIESEL": 1},
        base_sale_probability=probability, scenario_engine=ScenarioEngine(loader)), state


def test_scenario_schedule_uses_virtual_time_and_expires():
    engine, state = build(ScenarioType.FLOW_DROP)
    assert engine.run_tick(state).active_scenarios  # virtual time reaches START + 5 sec
    item = scenario(ScenarioType.FLOW_DROP, start=START + timedelta(seconds=10))
    assert ScenarioEngine(lambda moment: [] if moment < item.start_time else [item]).active(START + timedelta(seconds=5)) == []
    assert ScenarioEngine(lambda moment: [item] if moment < item.start_time + timedelta(minutes=1) else []).active(item.start_time)
    assert not ScenarioEngine(lambda moment: [item] if moment < item.start_time + timedelta(minutes=1) else []).active(item.start_time + timedelta(minutes=1))


def test_repository_sync_transitions_status_with_virtual_time():
    item = scenario(ScenarioType.FLOW_DROP)
    class Session:
        def scalars(self, _): return [item]
        def flush(self): pass
    repository = SimulationScenarioRepository(Session())
    assert repository.sync_for_time(1, START) == []
    assert item.status == SimulationStatus.CREATED
    assert repository.sync_for_time(1, item.start_time) == [item]
    assert item.status == SimulationStatus.RUNNING
    assert repository.sync_for_time(1, item.start_time + timedelta(minutes=1)) == []
    assert item.status == SimulationStatus.COMPLETED


def test_flow_drop_reduces_flow_and_high_current_is_bounded():
    normal, normal_state = build()
    affected, affected_state = build(ScenarioType.FLOW_DROP)
    assert affected.run_tick(affected_state).pump_results[0].flow_rate < normal.run_tick(normal_state).pump_results[0].flow_rate
    high, high_state = build(ScenarioType.HIGH_MOTOR_CURRENT)
    result = high.run_tick(high_state)
    assert 0 <= result.pump_results[0].motor_current <= high_state.pumps[1].maximum_motor_current
    assert result.pump_results[0].temperature > 0


def test_tank_and_sensor_scenarios_preserve_physical_bounds():
    stuck, stuck_state = build(ScenarioType.SENSOR_STUCK)
    first = stuck.run_tick(stuck_state).tank_results[0].measured_level_liters
    stuck.run_tick(stuck_state)
    assert stuck_state.tanks[1].measured_level_liters == first
    assert stuck_state.tanks[1].true_level_liters != first

    spike, spike_state = build(ScenarioType.SENSOR_SPIKE)
    before = spike_state.tanks[1].true_level_liters
    spike.run_tick(spike_state)
    assert spike_state.tanks[1].true_level_liters < before  # sales only; spike changes no physical level
    assert spike_state.tanks[1].measured_level_liters <= spike_state.tanks[1].capacity_liters

    leak, leak_state = build(ScenarioType.TANK_LEAK)
    leak_state.tanks[1].true_level_liters = 0.01
    leak.run_tick(leak_state)
    assert leak_state.tanks[1].true_level_liters >= 0


def test_water_rise_demand_surge_and_seed_are_deterministic():
    water, water_state = build(ScenarioType.WATER_LEVEL_RISE)
    water.run_tick(water_state)
    first = water_state.tanks[1].water_level
    water.run_tick(water_state)
    assert 0 < water_state.tanks[1].water_level - first <= 0.02
    assert ScenarioEngine(lambda _: [scenario(ScenarioType.DEMAND_SURGE)]).demand_multiplier([]) == 1.0
    assert ScenarioEngine(lambda _: [scenario(ScenarioType.DEMAND_SURGE)]).demand_multiplier([scenario(ScenarioType.DEMAND_SURGE)]) > 1.0
    profile = DemandProfile()
    normal_probability = profile.calculate_sale_probability(0.2, START.replace(hour=12), "DIESEL")
    surge_probability = profile.calculate_sale_probability(0.2, START.replace(hour=12), "DIESEL", 1.8)
    assert surge_probability > normal_probability
    one, one_state = build(ScenarioType.FLOW_DROP, seed=9)
    two, two_state = build(ScenarioType.FLOW_DROP, seed=9)
    assert [(x.flow_rate, x.motor_current) for x in one.run_tick(one_state).pump_results] == [(x.flow_rate, x.motor_current) for x in two.run_tick(two_state).pump_results]
