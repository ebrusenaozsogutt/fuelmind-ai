"""Bootstrap runtime simulation dependencies from persisted station records."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy import inspect, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.exceptions import BusinessRuleError, NotFoundError
from app.models.pump import Pump
from app.models.nozzle import Nozzle
from app.models.simulation_run import SimulationRun
from app.repositories.simulation_scenario_repository import SimulationScenarioRepository
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.repositories.simulation_run_repository import SimulationRunRepository
from app.simulation.clock import SimulationClock
from app.simulation.config import SimulationConfig
from app.simulation.delivery_generator import DeliveryGenerator
from app.simulation.demand_profile import DemandProfile
from app.simulation.pump_generator import PumpGenerator
from app.simulation.random_source import RandomSource
from app.simulation.runner import SimulationRunner
from app.simulation.sales_generator import SalesGenerator
from app.simulation.scenario_engine import ScenarioEngine
from app.simulation.state import (
    NozzleState,
    PumpState,
    StationSimulationState,
    TankProbeState,
    TankState,
)
from app.simulation.tank_generator import TankGenerator
from app.simulation.tick_engine import TickEngine
from app.simulation.validators import SimulationValidator
from app.services.commercial_sale_service import CommercialSaleService
from app.services.operations_selection_service import OperationsSelectionService

if TYPE_CHECKING:
    from app.live.event_broker import LiveEventBroker

SessionFactory = Callable[[], Session]


def build_simulation_runner(
    run_id: int,
    *,
    session_factory: SessionFactory = SessionLocal,
    config: SimulationConfig | None = None,
    live_event_broker: LiveEventBroker | None = None,
) -> SimulationRunner:
    """Build a standard realtime runner from one run and its station equipment."""

    session = session_factory()
    try:
        run = SimulationRunRepository(session).get(run_id)
        if run is None:
            raise NotFoundError(f"Simulation run {run_id} was not found.")
        state, fuel_codes = _build_station_state(session, run)
        runtime_config = config or simulation_config_from_run(run)
        scenarios_available = inspect(session.get_bind()).has_table("simulation_scenarios")
        operations_available = all(
            inspect(session.get_bind()).has_table(table_name)
            for table_name in (
                "attendants",
                "shifts",
                "attendant_shift_assignments",
            )
        )
        clock = SimulationClock(runtime_config, run.current_simulation_time)
        random_source = RandomSource(runtime_config.random_seed)
        prices = {code: 1.0 for code in fuel_codes.values()}
        def load_scenarios(moment):
            scenario_session = session_factory()
            try:
                scenarios = SimulationScenarioRepository(scenario_session).sync_for_time(run.id, moment)
                scenario_session.commit()
                return scenarios
            except OperationalError as exc:
                # Rolling deployments can briefly run a worker before the new table exists.
                # Preserve the Stage 1-6 tick path until Alembic has applied this migration.
                scenario_session.rollback()
                if "simulation_scenarios" in str(exc).lower():
                    return []
                raise
            except Exception:
                scenario_session.rollback()
                raise
            finally:
                scenario_session.close()

        tick_engine = TickEngine(
            config=runtime_config,
            clock=clock,
            sales_generator=SalesGenerator(
                random_source=random_source,
                demand_profile=DemandProfile(),
                commercial_selector=(
                    _commercial_selector(session_factory)
                    if run.mode.value == "REALTIME"
                    else None
                ),
                operations_selector=(
                    _operations_selector(session_factory) if operations_available else None
                ),
            ),
            tank_generator=TankGenerator(random_source=random_source),
            pump_generator=PumpGenerator(random_source=random_source),
            delivery_generator=DeliveryGenerator(random_source=random_source),
            validator=SimulationValidator(),
            fuel_codes_by_id=fuel_codes,
            unit_prices_by_fuel=prices,
            scenario_engine=ScenarioEngine(load_scenarios) if scenarios_available else ScenarioEngine(),
        )
        return SimulationRunner(
            run_id=run.id,
            station_state=state,
            tick_engine=tick_engine,
            session_factory=session_factory,
            mode=run.mode,
            live_event_broker=live_event_broker,
        )
    finally:
        session.close()


def _commercial_selector(session_factory: SessionFactory):
    """Open a short-lived read session for a simulated sale-start decision."""

    def select_context(**values):
        selection_session = session_factory()
        try:
            return CommercialSaleService(selection_session).prepare_simulation_sale(
                **values
            )
        finally:
            selection_session.close()

    return select_context


def _operations_selector(session_factory: SessionFactory):
    """Open a short-lived read session for a virtual-time attendant decision."""

    def select_context(**values):
        selection_session = session_factory()
        try:
            return OperationsSelectionService(selection_session).select_for_sale(**values)
        finally:
            selection_session.close()

    return select_context


def simulation_config_from_run(run: SimulationRun) -> SimulationConfig:
    """Convert the persisted runtime configuration of a run into Stage 3 config."""

    return SimulationConfig(
        tick_interval_seconds=run.tick_interval_ms / 1000,
        simulation_step_seconds=run.simulation_step_seconds,
        speed_multiplier=float(run.speed_multiplier),
        random_seed=run.random_seed,
        persist_every_n_ticks=run.persist_every_n_ticks,
    )


def _build_station_state(
    session: Session, run: SimulationRun
) -> tuple[StationSimulationState, dict[int, str]]:
    """Map persisted tanks and pumps to the unchanged Stage 3 state objects."""

    tanks = list(
        session.scalars(
            select(Tank).where(Tank.station_id == run.station_id).order_by(Tank.id)
        )
    )
    if not tanks:
        raise BusinessRuleError("A simulation station must have at least one tank.")
    state = StationSimulationState(
        station_id=run.station_id,
        sequence_number=run.sequence_number,
    )
    fuel_codes: dict[int, str] = {}
    for tank in tanks:
        code = tank.fuel_type.code
        fuel_codes[tank.fuel_type_id] = code
        state.add_tank(
            TankState(
                tank_id=tank.id,
                station_id=tank.station_id,
                fuel_type_id=tank.fuel_type_id,
                code=tank.code,
                capacity_liters=float(tank.capacity_liters),
                true_level_liters=float(tank.current_level_liters),
                measured_level_liters=float(tank.current_level_liters),
                minimum_safe_level=float(tank.minimum_safe_level),
                critical_level=float(tank.critical_level),
                temperature=float(tank.temperature or 0),
                water_level=float(tank.water_level),
                sensor_status=tank.sensor_status.value,
                is_active=tank.is_active,
            )
        )
    pumps = list(
        session.scalars(
            select(Pump).where(Pump.station_id == run.station_id).order_by(Pump.id)
        )
    )
    for pump in pumps:
        tank = state.get_tank(pump.tank_id)
        state.add_pump(
            PumpState(
                pump_id=pump.id,
                station_id=pump.station_id,
                tank_id=pump.tank_id,
                fuel_type_id=tank.fuel_type_id,
                code=pump.code,
                status=pump.status,
                nominal_flow_rate=float(pump.nominal_flow_rate),
                minimum_flow_rate=float(pump.minimum_flow_rate),
                maximum_motor_current=float(pump.maximum_motor_current),
                maximum_pressure=float(pump.maximum_pressure),
                total_working_hours=float(pump.total_working_hours),
                is_active=pump.is_active,
            )
        )
    inspector = inspect(session.get_bind())
    if inspector.has_table("tank_probes"):
        probes = list(
            session.scalars(
                select(TankProbe).where(
                    TankProbe.tank_id.in_(tuple(state.tanks)),
                    TankProbe.is_active.is_(True),
                )
            )
        )
        for probe in probes:
            state.add_active_probe(
                TankProbeState(
                    probe_id=probe.id,
                    tank_id=probe.tank_id,
                    status=probe.status,
                    is_active=probe.is_active,
                )
            )
    if inspector.has_table("nozzles"):
        nozzles = list(
            session.scalars(
                select(Nozzle).where(
                    Nozzle.pump_id.in_(tuple(state.pumps)),
                    Nozzle.is_active.is_(True),
                )
            )
        )
        for nozzle in nozzles:
            state.add_nozzle(
                NozzleState(
                    nozzle_id=nozzle.id,
                    pump_id=nozzle.pump_id,
                    fuel_type_id=nozzle.fuel_type_id,
                    status=nozzle.status,
                    is_active=nozzle.is_active,
                )
            )
    return state, fuel_codes
