"""Unit tests for the atomic simulation tick persistence boundary."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.simulation_run import SimulationRun
from app.simulation.delivery_generator import DeliveryResult
from app.simulation.enums import SourceType
from app.simulation.persistence import TickPersistence
from app.simulation.sales_generator import SaleAdvanceResult
from app.simulation.state import ActiveSaleState, PumpState, TankState
from app.simulation.tick_result import SimulationTickEvent, SimulationTickResult
from app.utils.enums import PumpStatus, SimulationStatus


class FakeSession:
    """Record unit-of-work operations without requiring a database backend."""

    def __init__(self, *, fail_flush: bool = False) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_flush = fail_flush

    def add_all(self, entities: list[object]) -> None:
        self.added.extend(entities)

    def flush(self) -> None:
        if self.fail_flush:
            raise RuntimeError("database write failed")

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeRunRepository:
    def __init__(self, _: FakeSession, run: SimulationRun) -> None:
        self.run = run

    def get_for_update(self, _: int) -> SimulationRun:
        return self.run


class FakeTankRepository:
    def __init__(self, _: FakeSession, tanks: dict[int, SimpleNamespace]) -> None:
        self.tanks = tanks

    def get_for_update(self, tank_id: int) -> SimpleNamespace | None:
        return self.tanks.get(tank_id)


@pytest.fixture
def persisted_tick(monkeypatch: pytest.MonkeyPatch) -> tuple[
    FakeSession, SimulationRun, SimulationTickResult, SimpleNamespace
]:
    """Provide one tick containing every persistence category."""

    now = datetime(2026, 8, 7, tzinfo=timezone.utc)
    tank_state = TankState(
        tank_id=11,
        station_id=7,
        fuel_type_id=3,
        code="T-11",
        capacity_liters=1000,
        true_level_liters=600,
        measured_level_liters=598,
        minimum_safe_level=200,
        critical_level=100,
        temperature=21.5,
        water_level=1.2,
        sensor_status="ACTIVE",
    )
    pump_state = PumpState(
        pump_id=21,
        station_id=7,
        tank_id=11,
        fuel_type_id=3,
        code="P-21",
        status=PumpStatus.IDLE,
        nominal_flow_rate=40,
        minimum_flow_rate=10,
        maximum_motor_current=10,
        maximum_pressure=8,
        flow_rate=0,
        pressure=2,
        motor_current=3,
        temperature=35,
        total_working_hours=12.5,
        error_count=1,
    )
    completed = ActiveSaleState(
        sale_id="SIM-7-21-000001",
        station_id=7,
        tank_id=11,
        pump_id=21,
        fuel_type_id=3,
        started_at=now - timedelta(minutes=2),
        target_quantity_liters=20,
        dispensed_quantity_liters=20,
        unit_price=42.5,
        last_updated_at=now,
    )
    delivery = DeliveryResult(
        delivery_id="DEL-7-11-001",
        station_id=7,
        tank_id=11,
        fuel_type_id=3,
        delivery_timestamp=now,
        requested_quantity_liters=100,
        delivered_quantity_liters=100,
        level_before_liters=500,
        level_after_liters=600,
        supplier_name="Demo supplier",
        source_type=SourceType.SIMULATION,
        is_automatic=True,
        was_clamped=False,
    )
    result = SimulationTickResult(
        station_id=7,
        simulation_time=now,
        sequence_number=1,
        tank_results=[tank_state],
        pump_results=[pump_state],
        sale_results=[SaleAdvanceResult(21, completed.sale_id, 20, completed)],
        completed_sales=[completed],
        deliveries=[delivery],
        events=[SimulationTickEvent("SALE_COMPLETED", 7, now, "PUMP", 21)],
    )
    run = SimulationRun(
        id=4,
        station_id=7,
        status=SimulationStatus.RUNNING,
        sequence_number=0,
        generated_sensor_count=0,
        generated_sale_count=0,
        generated_delivery_count=0,
    )
    database_tank = SimpleNamespace(id=11, station_id=7, current_level_liters=None)
    session = FakeSession()
    monkeypatch.setattr(
        "app.simulation.persistence.SimulationRunRepository",
        lambda db: FakeRunRepository(db, run),
    )
    monkeypatch.setattr(
        "app.simulation.persistence.TankRepository",
        lambda db: FakeTankRepository(db, {11: database_tank}),
    )
    return session, run, result, database_tank


def test_persist_tick_maps_all_categories_atomically(
    persisted_tick: tuple[FakeSession, SimulationRun, SimulationTickResult, SimpleNamespace],
) -> None:
    """One completed tick adds readings, sale, delivery, event, and run state."""

    session, run, result, database_tank = persisted_tick

    assert TickPersistence(session).persist(run.id, result)

    assert session.commits == 1
    assert session.rollbacks == 0
    assert len(session.added) == 5
    tank_reading, pump_reading, sale, delivery, event = session.added
    assert tank_reading.tank_level == 598
    assert tank_reading.true_tank_level == 600
    assert pump_reading.pump_temperature == 35
    assert sale.simulation_sale_id == "4-SIM-7-21-000001"
    assert sale.level_before == 520
    assert sale.level_after == 500
    assert delivery.simulation_delivery_id == "DEL-7-11-001"
    assert event.sequence_number == 1
    assert database_tank.current_level_liters == 600
    assert run.sequence_number == 1
    assert run.generated_sensor_count == 2
    assert run.generated_sale_count == 1
    assert run.generated_delivery_count == 1


def test_persist_tick_rolls_back_and_reraises_on_write_failure(
    persisted_tick: tuple[FakeSession, SimulationRun, SimulationTickResult, SimpleNamespace],
) -> None:
    """No partial write is committed if a database operation fails."""

    session, run, result, _ = persisted_tick
    session.fail_flush = True

    with pytest.raises(RuntimeError, match="database write failed"):
        TickPersistence(session).persist(run.id, result)

    assert session.commits == 0
    assert session.rollbacks == 1


def test_persistence_rejects_zero_quantity_completed_sale(
    persisted_tick: tuple[FakeSession, SimulationRun, SimulationTickResult, SimpleNamespace],
) -> None:
    """The persistence boundary must not turn an invalid domain result into a DB row."""

    session, run, result, _ = persisted_tick
    result.completed_sales[0].dispensed_quantity_liters = 0.0

    with pytest.raises(ValueError, match="positive dispensed quantity"):
        TickPersistence(session).persist(run.id, result)

    assert session.commits == 0
    assert session.rollbacks == 1


def test_persisted_tick_is_not_written_twice(
    persisted_tick: tuple[FakeSession, SimulationRun, SimulationTickResult, SimpleNamespace],
) -> None:
    """A retry of an already committed sequence is a no-op rather than a duplicate."""

    session, run, result, _ = persisted_tick
    persistence = TickPersistence(session)

    assert persistence.persist(run.id, result)
    assert not persistence.persist(run.id, result)
    assert len(session.added) == 5
    assert session.commits == 1
