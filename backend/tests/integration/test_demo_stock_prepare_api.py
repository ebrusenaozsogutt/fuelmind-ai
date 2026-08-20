"""Acceptance coverage for the API calls used by desktop demo stock preparation."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.delivery import Delivery
from app.models.fuel_type import FuelType
from app.models.simulation_run import SimulationRun
from app.models.station import Station
from app.models.tank import Tank
from app.models.user import User
from app.utils.enums import SensorStatus, UserRole


TABLES = [
    User.__table__,
    FuelType.__table__,
    Station.__table__,
    Tank.__table__,
    SimulationRun.__table__,
    Delivery.__table__,
]


@pytest.fixture
def demo_stock_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    user = User(
        username="demo-stock-operator",
        password_hash="x",
        full_name="Demo Stock Operator",
        role=UserRole.OPERATOR,
    )
    fuel = FuelType(name="Diesel", code="DSL")
    station = Station(
        code="DEMO-1",
        name="Demo Station",
        city="Konya",
        district="Selçuklu",
        address="Demo address",
    )
    session.add_all([user, fuel, station])
    session.flush()
    tank = Tank(
        station_id=station.id,
        fuel_type_id=fuel.id,
        code="T-1",
        capacity_liters=Decimal("1000"),
        current_level_liters=Decimal("400"),
        minimum_safe_level=Decimal("200"),
        critical_level=Decimal("100"),
        water_level=Decimal("0"),
        sensor_status=SensorStatus.ACTIVE,
    )
    session.add(tank)
    session.commit()
    ids = {"station": station.id, "tank": tank.id}
    session.close()

    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_operator_or_admin] = lambda: user
    try:
        with TestClient(app) as client:
            yield client, factory, ids
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(TABLES)))
        engine.dispose()


def test_demo_stock_prerequisite_accepts_no_active_run_and_persists_delivery(demo_stock_api):
    """The desktop flow can proceed after ``200 null`` and stock is then initialized."""

    client, factory, ids = demo_stock_api

    active = client.get("/api/simulations/active", params={"station_id": ids["station"]})
    assert active.status_code == 200
    assert active.json() is None

    created = client.post(
        "/api/deliveries",
        json={
            "tank_id": ids["tank"],
            "delivery_timestamp": "2026-08-19T09:00:00+00:00",
            "quantity_liters": "250",
            "supplier_name": "Demo stock preparation",
        },
    )
    assert created.status_code == 201
    assert created.json()["level_before"] == "400.000"
    assert created.json()["level_after"] == "650.000"

    session = factory()
    try:
        assert session.get(Tank, ids["tank"]).current_level_liters == Decimal("650")
        assert session.query(Delivery).filter_by(tank_id=ids["tank"]).count() == 1
    finally:
        session.close()
