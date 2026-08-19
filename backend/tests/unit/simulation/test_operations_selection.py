"""Virtual-time attendant and shift selection coverage for simulated sales."""

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.live.serializers import serialize_simulation_tick
from app.models.operations import Attendant, AttendantShiftAssignment, Shift
from app.models.station import Station
from app.services.operations_selection_service import OperationsSelectionService
from app.simulation import (
    DemandProfile,
    PumpState,
    RandomSource,
    SalesGenerator,
    StationSimulationState,
    TankState,
)
from app.simulation.sales_generator import SaleAdvanceResult
from app.simulation.state import ActiveSaleState
from app.simulation.tick_result import SimulationTickResult
from app.utils.enums import PumpStatus


@pytest.fixture
def operations_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        Station.__table__,
        Attendant.__table__,
        Shift.__table__,
        AttendantShiftAssignment.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(bind=engine)
    session = factory()
    primary = Station(code="OPS-1", name="Primary", city="Konya", district="A", address="A")
    other = Station(code="OPS-2", name="Other", city="Konya", district="B", address="B")
    session.add_all([primary, other])
    session.flush()
    shifts = {
        "MORNING": Shift(station_id=primary.id, code="MORNING", name="Morning", start_time=time(8), end_time=time(16)),
        "EVENING": Shift(station_id=primary.id, code="EVENING", name="Evening", start_time=time(16), end_time=time(0)),
        "NIGHT": Shift(station_id=primary.id, code="NIGHT", name="Night", start_time=time(0), end_time=time(8)),
    }
    attendants = [
        Attendant(station_id=primary.id, code="A-1", full_name="Morning One", employee_number="EMP-1"),
        Attendant(station_id=primary.id, code="A-2", full_name="Morning Two", employee_number="EMP-2"),
        Attendant(station_id=primary.id, code="A-3", full_name="Evening One", employee_number="EMP-3"),
        Attendant(station_id=primary.id, code="A-4", full_name="Night One", employee_number="EMP-4"),
        Attendant(station_id=other.id, code="A-OTHER", full_name="Other Station", employee_number="EMP-OTHER"),
    ]
    session.add_all([*shifts.values(), *attendants])
    session.flush()
    session.add_all(
        [
            AttendantShiftAssignment(station_id=primary.id, attendant_id=attendants[0].id, shift_id=shifts["MORNING"].id),
            AttendantShiftAssignment(station_id=primary.id, attendant_id=attendants[1].id, shift_id=shifts["MORNING"].id),
            AttendantShiftAssignment(station_id=primary.id, attendant_id=attendants[2].id, shift_id=shifts["EVENING"].id),
            AttendantShiftAssignment(station_id=primary.id, attendant_id=attendants[3].id, shift_id=shifts["NIGHT"].id),
        ]
    )
    session.commit()
    try:
        yield session, primary, other, shifts
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(tables)))
        engine.dispose()


@pytest.mark.parametrize(
    ("moment", "expected_shift"),
    [
        (datetime(2026, 8, 1, 9, tzinfo=timezone.utc), "MORNING"),
        (datetime(2026, 8, 1, 18, tzinfo=timezone.utc), "EVENING"),
        (datetime(2026, 8, 2, 0, tzinfo=timezone.utc), "NIGHT"),
        (datetime(2026, 8, 2, 7, 59, tzinfo=timezone.utc), "NIGHT"),
    ],
)
def test_virtual_clock_resolves_active_shift(operations_session, moment, expected_shift) -> None:
    session, station, _, shifts = operations_session
    selection = OperationsSelectionService(session).select_for_sale(
        station_id=station.id,
        simulation_time=moment,
        random_source=RandomSource(4),
    )

    assert selection is not None
    assert selection.shift_id == shifts[expected_shift].id


def test_selection_is_station_scoped_and_deterministic(operations_session) -> None:
    session, station, other, _ = operations_session
    service = OperationsSelectionService(session)
    moment = datetime(2026, 8, 1, 9, tzinfo=timezone.utc)
    first_random = RandomSource(19)
    second_random = RandomSource(19)

    first = [
        service.select_for_sale(station_id=station.id, simulation_time=moment, random_source=first_random)
        for _ in range(5)
    ]
    second = [
        service.select_for_sale(station_id=station.id, simulation_time=moment, random_source=second_random)
        for _ in range(5)
    ]

    assert first == second
    assert all(item is not None and item.attendant_name != "OTHER STATION" for item in first)
    assert service.select_for_sale(
        station_id=other.id, simulation_time=moment, random_source=RandomSource(19)
    ) is None


def _station_state() -> StationSimulationState:
    state = StationSimulationState(station_id=1)
    state.add_tank(TankState(1, 1, 1, "T-1", 1_000, 500, 500, 100, 50, 20, 0, "OK"))
    state.add_pump(PumpState(1, 1, 1, 1, "P-1", PumpStatus.IDLE, 42, 10, 20, 8))
    return state


def test_active_sale_keeps_start_selection_when_shift_changes() -> None:
    def selection_service(**_):
        return type(
            "Selection",
            (),
            {
                "attendant_id": 3,
                "attendant_name": "Morning",
                "shift_id": 7,
                "shift_name": "Morning Shift",
            },
        )()

    generator = SalesGenerator(
        random_source=RandomSource(7),
        demand_profile=DemandProfile(),
        operations_selector=selection_service,
    )
    started_at = datetime(2026, 8, 1, 15, 59, tzinfo=timezone.utc)
    station_state = _station_state()
    sale = generator.try_start_sale(
        station_state=station_state,
        pump_id=1,
        moment=started_at,
        base_probability=1,
        fuel_code="DIESEL",
        unit_price=45,
    )
    assert sale is not None
    sale.target_quantity_liters = 100
    result = generator.advance_active_sale(
        station_state=station_state,
        pump_id=1,
        elapsed_seconds=1,
        updated_at=started_at + timedelta(minutes=2),
    )
    assert result.completed_sale is None
    assert (sale.attendant_id, sale.shift_id) == (3, 7)


def test_legacy_station_without_operations_still_generates_sales() -> None:
    generator = SalesGenerator(
        random_source=RandomSource(7),
        demand_profile=DemandProfile(),
        operations_selector=lambda **_: None,
    )
    sale = generator.try_start_sale(
        station_state=_station_state(),
        pump_id=1,
        moment=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        base_probability=1,
        fuel_code="DIESEL",
        unit_price=45,
    )

    assert sale is not None
    assert sale.attendant_id is None
    assert sale.shift_id is None


def test_live_sale_payload_adds_operational_context() -> None:
    moment = datetime(2026, 8, 1, 9, tzinfo=timezone.utc)
    sale = ActiveSaleState(
        "SIM-OPS-1", 1, 1, 1, 1, moment, 10, 10, 45, moment,
        attendant_id=2, attendant_name="Morning One", shift_id=3, shift_name="Morning",
    )
    tank = TankState(1, 1, 1, "T-1", 1_000, 490, 490, 100, 50, 20, 0, "OK")
    pump = PumpState(1, 1, 1, 1, "P-1", PumpStatus.IDLE, 42, 10, 20, 8)
    result = SimulationTickResult(
        1, moment, 1, [tank], [pump],
        [SaleAdvanceResult(1, sale.sale_id, 10, sale)], [sale], [], [],
    )

    payload = serialize_simulation_tick(1, result, generated_at=moment)
    assert payload["sales"][0]["attendant_id"] == 2
    assert payload["sales"][0]["shift_id"] == 3
    assert payload["sales"][0]["attendant_name"] == "Morning One"
    assert payload["sales"][0]["shift_name"] == "Morning"
