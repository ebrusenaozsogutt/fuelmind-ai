"""Integration coverage for the atomic card-backed commercial sale endpoint."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.commercial import (
    Customer,
    Driver,
    DriverVehicleAssignment,
    Fleet,
    FleetGroup,
    FuelCard,
    FuelCardAllowedFuelType,
    FuelCardAllowedStation,
    FuelCardLimit,
    FuelCardUsageWindow,
    FuelPrice,
    Vehicle,
)
from app.models.fuel_type import FuelType
from app.models.delivery import Delivery
from app.models.nozzle import Nozzle
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.station import Station
from app.models.tank import Tank
from app.services.commercial_sale_service import CommercialSaleService
from app.services.tank_reconciliation_service import TankReconciliationService
from app.simulation.random_source import RandomSource
from app.utils.enums import (
    CardLimitType,
    CardStatus,
    CustomerType,
    DriverAssignmentStatus,
    NozzleStatus,
    PaymentType,
    PumpStatus,
    SensorStatus,
)


TABLES = [
    Customer.__table__,
    Fleet.__table__,
    FleetGroup.__table__,
    Vehicle.__table__,
    Driver.__table__,
    DriverVehicleAssignment.__table__,
    FuelCard.__table__,
    FuelCardAllowedStation.__table__,
    FuelCardAllowedFuelType.__table__,
    FuelCardLimit.__table__,
    FuelCardUsageWindow.__table__,
    Station.__table__,
    FuelType.__table__,
    Tank.__table__,
    Pump.__table__,
    Nozzle.__table__,
    FuelPrice.__table__,
    Sale.__table__,
    Delivery.__table__,
]


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(TABLES)))
        engine.dispose()


def seed_commercial_context(factory, *, payment_type=PaymentType.PREPAID, balance="5000"):
    """Seed a complete trusted commercial hierarchy and compatible nozzle."""

    session = factory()
    customer = Customer(
        code="KONYA-LOJISTIK",
        name="Konya Lojistik",
        customer_type=CustomerType.COMPANY,
        discount_rate=Decimal("3"),
    )
    station = Station(
        code="KONYA-TEST",
        name="Konya Test",
        city="Konya",
        district="Selcuklu",
        address="Test",
    )
    fuel = FuelType(name="Motorin", code="MOTORIN")
    session.add_all([customer, station, fuel])
    session.flush()
    fleet = Fleet(customer_id=customer.id, code="KONYA", name="Konya Filosu")
    session.add(fleet)
    session.flush()
    group = FleetGroup(fleet_id=fleet.id, code="AGIR", name="Ağır Vasıta")
    session.add(group)
    session.flush()
    vehicle = Vehicle(fleet_group_id=group.id, plate="42 DEMO 01")
    driver = Driver(full_name="Demo Şoför", reference_code="DRV-1")
    session.add_all([vehicle, driver])
    session.flush()
    assignment = DriverVehicleAssignment(
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        assigned_from=date(2020, 1, 1),
        status=DriverAssignmentStatus.ACTIVE,
    )
    tank = Tank(
        station_id=station.id,
        fuel_type_id=fuel.id,
        code="TANK-1",
        capacity_liters=Decimal("10000"),
        current_level_liters=Decimal("8000"),
        minimum_safe_level=Decimal("1000"),
        critical_level=Decimal("500"),
        water_level=Decimal("0"),
        sensor_status=SensorStatus.ACTIVE,
    )
    session.add_all([assignment, tank])
    session.flush()
    pump = Pump(
        station_id=station.id,
        tank_id=tank.id,
        code="PUMP-1",
        status=PumpStatus.IDLE,
        nominal_flow_rate=Decimal("45"),
        minimum_flow_rate=Decimal("10"),
        maximum_motor_current=Decimal("18"),
        maximum_pressure=Decimal("8"),
        total_working_hours=Decimal("0"),
    )
    session.add(pump)
    session.flush()
    nozzle = Nozzle(
        pump_id=pump.id,
        fuel_type_id=fuel.id,
        code="NOZZLE-1",
        nozzle_number=1,
        status=NozzleStatus.AVAILABLE,
        totalizer_liters=Decimal("100000"),
    )
    card = FuelCard(
        vehicle_id=vehicle.id,
        card_code="DEMO-CARD-01",
        display_name="Demo Card",
        unit_id="UNIT-DEMO-001",
        status=CardStatus.ACTIVE,
        valid_from=date(2020, 1, 1),
        payment_type=payment_type,
        prepaid_balance=Decimal(balance) if payment_type == PaymentType.PREPAID else Decimal("0"),
        credit_limit=Decimal(balance) if payment_type == PaymentType.CREDIT else Decimal("0"),
    )
    price = FuelPrice(
        station_id=station.id,
        fuel_type_id=fuel.id,
        unit_price=Decimal("55"),
        effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        is_active=True,
    )
    session.add_all([nozzle, card, price])
    session.flush()
    session.add_all(
        [
            FuelCardAllowedStation(fuel_card_id=card.id, station_id=station.id),
            FuelCardAllowedFuelType(fuel_card_id=card.id, fuel_type_id=fuel.id),
        ]
    )
    session.commit()
    result = {"card": card.id, "nozzle": nozzle.id, "driver": driver.id}
    session.close()
    return result


def request(nozzle_id: int, quantity: str = "40") -> dict[str, object]:
    return {
        "unit_id": "unit-demo-001",
        "nozzle_id": nozzle_id,
        "quantity_liters": quantity,
        "started_at": "2030-01-01T10:00:00+00:00",
    }


def test_prepaid_sale_persists_commercial_and_totalizer_snapshots(api):
    client, factory = api
    ids = seed_commercial_context(factory)
    response = client.post("/api/sales/commercial", json=request(ids["nozzle"]))
    assert response.status_code == 200
    body = response.json()
    assert body["completed"] is True
    sale = body["sale"]
    assert sale["fuel_card_id"] == ids["card"]
    assert sale["driver_id"] == ids["driver"]
    assert sale["start_totalizer_liters"] == "100000.000"
    assert sale["end_totalizer_liters"] == "100040.000"
    assert sale["list_unit_price"] == "55.0000"
    assert sale["discount_rate"] == "3.00"
    assert sale["unit_price"] == "53.3500"
    assert sale["total_amount"] == "2134.00"
    assert sale["payment_type"] == "PREPAID"

    session = factory()
    card = session.get(FuelCard, ids["card"])
    nozzle = session.get(Nozzle, ids["nozzle"])
    assert card.prepaid_balance == Decimal("2866.00")
    assert nozzle.totalizer_liters == Decimal("100040.000")
    assert session.get(Tank, sale["tank_id"]).current_level_liters == Decimal("7960.000")
    session.close()


def test_completed_sale_reconciles_against_stock_and_deliveries(api):
    client, factory = api
    ids = seed_commercial_context(factory)
    assert client.post("/api/sales/commercial", json=request(ids["nozzle"], "40")).json()["completed"]
    session = factory()
    sale = session.query(Sale).one()
    result = TankReconciliationService(session).reconcile(
        tank_id=sale.tank_id,
        period_start=datetime(2030, 1, 1, 9, tzinfo=timezone.utc),
        period_end=datetime(2030, 1, 1, 11, tzinfo=timezone.utc),
        opening_level_liters=Decimal("8000"),
        actual_closing_level_liters=Decimal("7960"),
        raise_alarm=False,
    )
    assert result.completed_sales_liters == Decimal("40.000")
    assert result.delivery_liters == Decimal("0.000")
    assert result.expected_closing_level_liters == Decimal("7960.000")
    assert result.difference_liters == Decimal("0.000")
    assert result.is_reconciled is True
    session.close()


def test_second_sale_uses_previous_end_totalizer_and_completed_sale_consumes_limit(api):
    client, factory = api
    ids = seed_commercial_context(factory)
    session = factory()
    session.add(
        FuelCardLimit(
            fuel_card_id=ids["card"],
            limit_type=CardLimitType.DAILY,
            quantity_limit_liters=Decimal("100"),
        )
    )
    session.commit()
    session.close()
    first = client.post("/api/sales/commercial", json=request(ids["nozzle"], "60"))
    assert first.json()["completed"] is True
    second = client.post("/api/sales/commercial", json=request(ids["nozzle"], "30"))
    assert second.json()["sale"]["start_totalizer_liters"] == "100060.000"
    rejected = client.post("/api/sales/commercial", json=request(ids["nozzle"], "20"))
    assert rejected.json()["completed"] is False
    assert rejected.json()["decision_code"] == "DAILY_LIMIT_EXCEEDED"


def test_insufficient_prepaid_rejection_leaves_card_sale_and_totalizer_unchanged(api):
    client, factory = api
    ids = seed_commercial_context(factory, balance="100")
    response = client.post("/api/sales/commercial", json=request(ids["nozzle"]))
    assert response.status_code == 200
    assert response.json()["decision_code"] == "INSUFFICIENT_PREPAID_BALANCE"
    session = factory()
    assert session.query(Sale).count() == 0
    assert session.get(FuelCard, ids["card"]).prepaid_balance == Decimal("100")
    assert session.get(Nozzle, ids["nozzle"]).totalizer_liters == Decimal("100000")
    session.close()


def test_simulation_sale_selection_falls_back_from_insufficient_prepaid_card(api):
    _, factory = api
    ids = seed_commercial_context(factory, balance="100")
    session = factory()
    first_card = session.get(FuelCard, ids["card"])
    nozzle = session.get(Nozzle, ids["nozzle"])
    assert first_card is not None and nozzle is not None
    fallback = FuelCard(
        vehicle_id=first_card.vehicle_id,
        card_code="DEMO-CARD-FALLBACK",
        display_name="Fallback demo card",
        unit_id="UNIT-DEMO-FALLBACK",
        status=CardStatus.ACTIVE,
        valid_from=date(2020, 1, 1),
        payment_type=PaymentType.PREPAID,
        prepaid_balance=Decimal("5000"),
    )
    session.add(fallback)
    session.flush()
    session.add_all([
        FuelCardAllowedStation(fuel_card_id=fallback.id, station_id=nozzle.pump.station_id),
        FuelCardAllowedFuelType(fuel_card_id=fallback.id, fuel_type_id=nozzle.fuel_type_id),
    ])
    session.commit()

    selection = CommercialSaleService(session).prepare_simulation_sale(
        station_id=nozzle.pump.station_id,
        fuel_type_id=nozzle.fuel_type_id,
        quantity_liters=Decimal("40"),
        started_at=datetime(2030, 1, 1, 10, tzinfo=timezone.utc),
        random_source=RandomSource(42),
    )

    assert selection.snapshot is not None
    assert selection.snapshot.fuel_card_id == fallback.id
    assert first_card.prepaid_balance == Decimal("100")
    session.close()


def test_credit_sale_uses_credit_used_and_enforces_available_boundary(api):
    client, factory = api
    ids = seed_commercial_context(factory, payment_type=PaymentType.CREDIT, balance="2200")
    success = client.post("/api/sales/commercial", json=request(ids["nozzle"]))
    assert success.json()["completed"] is True
    session = factory()
    assert session.get(FuelCard, ids["card"]).credit_used == Decimal("2134.00")
    session.close()
    rejected = client.post("/api/sales/commercial", json=request(ids["nozzle"], "2"))
    assert rejected.json()["decision_code"] == "CREDIT_LIMIT_EXCEEDED"
