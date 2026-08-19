"""Integration coverage for persisted field-device simulation effects."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.operations import Attendant, AttendantShiftAssignment, Shift
from app.models.probe_reading import ProbeReading
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.sensor_reading import SensorReading
from app.models.simulation_run import SimulationRun
from app.models.station import Station
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.models.user import User
from app.simulation import (
    DeliveryGenerator,
    DemandProfile,
    PumpGenerator,
    RandomSource,
    SalesGenerator,
    SimulationClock,
    SimulationConfig,
    SimulationValidator,
    TankGenerator,
    TickEngine,
)
from app.simulation.dependencies import _build_station_state, _operations_selector
from app.simulation.persistence import TickPersistence
from app.simulation.sales_generator import SaleAdvanceResult
from app.simulation.state import ActiveSaleState, PumpState, TankState
from app.simulation.tick_result import SimulationTickResult
from app.utils.enums import NozzleStatus, ProbeStatus, PumpStatus, SimulationStatus

_TABLES = [
    User.__table__,
    Station.__table__,
    FuelType.__table__,
    Tank.__table__,
    Pump.__table__,
    TankProbe.__table__,
    Nozzle.__table__,
    Attendant.__table__,
    Shift.__table__,
    AttendantShiftAssignment.__table__,
    SimulationRun.__table__,
    SensorReading.__table__,
    ProbeReading.__table__,
    Sale.__table__,
]


@pytest.fixture
def field_simulation_db():
    """Seed a minimal persisted topology suitable for actual ticks."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    station = Station(code="S-1", name="Station", city="A", district="A", address="A")
    fuel = FuelType(name="Diesel", code="DIESEL")
    session.add_all([station, fuel])
    session.flush()
    attendant = Attendant(
        station_id=station.id,
        code="ATT-1",
        full_name="Simulation Attendant",
        employee_number="SIM-ATT-1",
    )
    morning_shift = Shift(
        station_id=station.id,
        code="MORNING",
        name="Morning Shift",
        start_time=datetime.strptime("08:00", "%H:%M").time(),
        end_time=datetime.strptime("16:00", "%H:%M").time(),
    )
    session.add_all([attendant, morning_shift])
    session.flush()
    session.add(
        AttendantShiftAssignment(
            station_id=station.id,
            attendant_id=attendant.id,
            shift_id=morning_shift.id,
        )
    )
    tank = Tank(
        station_id=station.id,
        fuel_type_id=fuel.id,
        code="T-1",
        capacity_liters=Decimal("1000"),
        current_level_liters=Decimal("650"),
        minimum_safe_level=Decimal("100"),
        critical_level=Decimal("50"),
        temperature=Decimal("18.7"),
        water_level=Decimal("5"),
    )
    session.add(tank)
    session.flush()
    pump = Pump(
        station_id=station.id,
        tank_id=tank.id,
        code="P-1",
        status=PumpStatus.IDLE,
        nominal_flow_rate=Decimal("42"),
        minimum_flow_rate=Decimal("10"),
        maximum_motor_current=Decimal("20"),
        maximum_pressure=Decimal("8"),
    )
    session.add(pump)
    session.flush()
    probe = TankProbe(
        tank_id=tank.id,
        code="PRB-1",
        name="Probe",
        status=ProbeStatus.ONLINE,
        is_active=True,
    )
    nozzle = Nozzle(
        pump_id=pump.id,
        fuel_type_id=fuel.id,
        code="NZL-1",
        nozzle_number=1,
        status=NozzleStatus.AVAILABLE,
        totalizer_liters=Decimal("100"),
        is_active=True,
    )
    run = SimulationRun(
        station_id=station.id,
        status=SimulationStatus.RUNNING,
        current_simulation_time=datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
    )
    session.add_all([probe, nozzle, run])
    session.commit()
    try:
        yield factory, session, {"station": station, "tank": tank, "pump": pump, "probe": probe, "nozzle": nozzle, "run": run, "attendant": attendant, "shift": morning_shift}
    finally:
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()


def _engine(
    start: datetime,
    *,
    operations_selector: object | None = None,
    simulation_step_seconds: int = 5,
    base_sale_probability: float = 0,
) -> TickEngine:
    config = SimulationConfig(simulation_step_seconds=simulation_step_seconds, random_seed=7)
    random_source = RandomSource(config.random_seed)
    return TickEngine(
        config=config,
        clock=SimulationClock(config, start),
        sales_generator=SalesGenerator(
            random_source=random_source,
            demand_profile=DemandProfile(),
            operations_selector=operations_selector,
        ),
        tank_generator=TankGenerator(random_source=random_source),
        pump_generator=PumpGenerator(random_source=random_source),
        delivery_generator=DeliveryGenerator(random_source=random_source),
        validator=SimulationValidator(),
        fuel_codes_by_id={1: "DIESEL"},
        unit_prices_by_fuel={"DIESEL": 45},
        base_sale_probability=base_sale_probability,
    )


def _completed_result(
    *, station_id: int, tank_id: int, pump_id: int, nozzle_id: int, moment: datetime, sequence: int, quantity: float
) -> SimulationTickResult:
    tank = TankState(tank_id, station_id, 1, "T-1", 1_000, 650, 648, 100, 50, 18.7, 5, "OK")
    pump = PumpState(pump_id, station_id, tank_id, 1, "P-1", PumpStatus.IDLE, 42, 10, 20, 8)
    completed = ActiveSaleState(
        sale_id=f"SIM-{sequence}",
        station_id=station_id,
        tank_id=tank_id,
        pump_id=pump_id,
        fuel_type_id=1,
        started_at=moment - timedelta(seconds=10),
        target_quantity_liters=quantity,
        dispensed_quantity_liters=quantity,
        unit_price=45,
        nozzle_id=nozzle_id,
        last_updated_at=moment,
    )
    return SimulationTickResult(
        station_id=station_id,
        simulation_time=moment,
        sequence_number=sequence,
        tank_results=[tank],
        pump_results=[pump],
        sale_results=[SaleAdvanceResult(pump_id, completed.sale_id, quantity, completed)],
        completed_sales=[completed],
        deliveries=[],
        events=[],
    )


def test_simulated_probe_readings_are_persisted_and_available_through_rest(field_simulation_db) -> None:
    factory, session, data = field_simulation_db
    state, fuel_codes = _build_station_state(session, data["run"])
    assert state.active_probes_by_tank[data["tank"].id].probe_id == data["probe"].id
    assert state.available_nozzles(data["pump"].id)[0].nozzle_id == data["nozzle"].id
    engine = _engine(data["run"].current_simulation_time)

    for _ in range(3):
        TickPersistence(session).persist(data["run"].id, engine.run_tick(state))

    reading = session.scalar(select(ProbeReading).order_by(ProbeReading.sequence_number.desc()))
    assert reading is not None
    expected_volume = Decimal(
        str(state.get_tank(data["tank"].id).measured_level_liters)
    ).quantize(Decimal("0.001"))
    assert reading.fuel_volume_liters == expected_volume
    # SQLite does not round-trip timezone metadata, unlike the production database.
    assert reading.reading_timestamp.replace(
        tzinfo=timezone.utc
    ) == data["run"].current_simulation_time
    assert reading.sequence_number == data["run"].sequence_number
    assert reading.data_quality_score == Decimal("100")

    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    with TestClient(app) as client:
        response = client.get(f"/api/tank-probes/{data['probe'].id}/readings")
        tank_response = client.get(f"/api/tanks/{data['tank'].id}/probe-readings")
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert len(tank_response.json()) == 3
    assert response.json()[0]["sequence_number"] == 3


def test_completed_sale_updates_nozzle_totalizer_atomically(field_simulation_db, monkeypatch: pytest.MonkeyPatch) -> None:
    factory, session, data = field_simulation_db
    run = data["run"]
    first = _completed_result(
        station_id=data["station"].id,
        tank_id=data["tank"].id,
        pump_id=data["pump"].id,
        nozzle_id=data["nozzle"].id,
        moment=run.current_simulation_time + timedelta(seconds=5),
        sequence=1,
        quantity=12.5,
    )
    second = _completed_result(
        station_id=data["station"].id,
        tank_id=data["tank"].id,
        pump_id=data["pump"].id,
        nozzle_id=data["nozzle"].id,
        moment=run.current_simulation_time + timedelta(seconds=10),
        sequence=2,
        quantity=7.5,
    )

    persistence = TickPersistence(session)
    assert persistence.persist(run.id, first)
    assert persistence.persist(run.id, second)
    assert session.get(Nozzle, data["nozzle"].id).totalizer_liters == Decimal("120.000")

    failed = _completed_result(
        station_id=data["station"].id,
        tank_id=data["tank"].id,
        pump_id=data["pump"].id,
        nozzle_id=data["nozzle"].id,
        moment=run.current_simulation_time + timedelta(seconds=15),
        sequence=3,
        quantity=4,
    )
    monkeypatch.setattr(persistence, "_update_tank_levels", lambda _: (_ for _ in ()).throw(RuntimeError("forced rollback")))
    with pytest.raises(RuntimeError, match="forced rollback"):
        persistence.persist(run.id, failed)

    verification = factory()
    try:
        assert verification.get(Nozzle, data["nozzle"].id).totalizer_liters == Decimal("120.000")
        assert verification.scalar(select(func.count()).select_from(Sale)) == 2
    finally:
        verification.close()


def test_real_simulation_ticks_persist_selected_attendant_and_shift(field_simulation_db) -> None:
    """Several genuine ticks retain virtual-time operational context in each sale."""

    factory, session, data = field_simulation_db
    run = data["run"]
    run.current_simulation_time = datetime(2026, 8, 14, 8, 45, tzinfo=timezone.utc)
    session.commit()
    state, _ = _build_station_state(session, run)

    engine = _engine(
        run.current_simulation_time,
        operations_selector=_operations_selector(factory),
        simulation_step_seconds=300,
        base_sale_probability=1,
    )
    persistence = TickPersistence(session)
    for _ in range(3):
        result = engine.run_tick(state)
        result.events = []
        assert persistence.persist(run.id, result)

    sales = list(session.scalars(select(Sale).order_by(Sale.id)))
    assert len(sales) == 3
    assert all(sale.attendant_id == data["attendant"].id for sale in sales)
    assert all(sale.shift_id == data["shift"].id for sale in sales)
    assert all(
        sale.quantity_liters == sale.end_totalizer_liters - sale.start_totalizer_liters
        for sale in sales
    )
    assert all(
        sale.total_amount
        == (sale.quantity_liters * sale.unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        for sale in sales
    )
