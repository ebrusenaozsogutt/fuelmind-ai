"""Focused integration tests for fuel price history and pricing previews."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.commercial import Customer, FuelPrice
from app.models.audit_log import AuditLog
from app.models.fuel_type import FuelType
from app.models.station import Station
from app.models.user import User
from app.services.audit_service import AuditService
from app.utils.enums import AuditAction, CustomerType, UserRole


TABLES = [
    User.__table__,
    Customer.__table__,
    Station.__table__,
    FuelType.__table__,
    FuelPrice.__table__,
    AuditLog.__table__,
]


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_, __, **___):
    return "JSON"


def timestamp(value: str) -> str:
    """Return a UTC ISO timestamp from a compact test date string."""

    return f"{value}+00:00"


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    admin = User(
        username="price-admin",
        password_hash="hash",
        full_name="Price Admin",
        role=UserRole.ADMIN,
    )
    session.add(admin)
    session.commit()
    session.close()

    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[require_operator_or_admin] = lambda: admin
    try:
        with TestClient(app) as client:
            yield client, factory, admin
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(TABLES)))
        engine.dispose()


def seed_pricing_data(factory):
    """Create one customer, station, and fuel type for a test scenario."""

    session = factory()
    customer = Customer(
        code="PRICE-CUSTOMER",
        name="Price Customer",
        customer_type=CustomerType.COMPANY,
        discount_rate=Decimal("3"),
    )
    station = Station(
        code="KONYA-TEST",
        name="Konya Test",
        city="Konya",
        district="Selcuklu",
        address="Test address",
    )
    fuel_type = FuelType(name="Motorin", code="MOTORIN")
    session.add_all([customer, station, fuel_type])
    session.commit()
    values = customer.id, station.id, fuel_type.id
    session.close()
    return values


def price_payload(station_id: int, fuel_type_id: int, **overrides: object) -> dict[str, object]:
    """Build a valid future price payload with easy per-test overrides."""

    payload: dict[str, object] = {
        "station_id": station_id,
        "fuel_type_id": fuel_type_id,
        "unit_price": "55.0000",
        "effective_from": timestamp("2030-01-01T00:00:00"),
        "effective_until": None,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def test_admin_creates_price_and_auto_closes_previous_open_price(api):
    client, factory, admin = api
    _, station_id, fuel_type_id = seed_pricing_data(factory)

    first = client.post("/api/fuel-prices", json=price_payload(station_id, fuel_type_id))
    assert first.status_code == 201
    assert first.json()["created_by"] == admin.id

    second = client.post(
        "/api/fuel-prices",
        json=price_payload(
            station_id,
            fuel_type_id,
            unit_price="56.0000",
            effective_from=timestamp("2030-02-01T00:00:00"),
        ),
    )
    assert second.status_code == 201
    history = client.get(
        f"/api/stations/{station_id}/fuel-prices/{fuel_type_id}/history"
    )
    assert history.status_code == 200
    assert [row["unit_price"] for row in history.json()] == ["56.0000", "55.0000"]
    assert history.json()[1]["effective_until"].startswith("2030-02-01T00:00:00")


def test_adjacent_periods_are_valid_but_overlaps_are_rejected(api):
    client, factory, _ = api
    _, station_id, fuel_type_id = seed_pricing_data(factory)
    first = price_payload(
        station_id,
        fuel_type_id,
        effective_until=timestamp("2030-02-01T00:00:00"),
    )
    assert client.post("/api/fuel-prices", json=first).status_code == 201
    adjacent = price_payload(
        station_id,
        fuel_type_id,
        unit_price="56",
        effective_from=timestamp("2030-02-01T00:00:00"),
        effective_until=timestamp("2030-03-01T00:00:00"),
    )
    assert client.post("/api/fuel-prices", json=adjacent).status_code == 201
    overlap = price_payload(
        station_id,
        fuel_type_id,
        unit_price="57",
        effective_from=timestamp("2030-02-15T00:00:00"),
    )
    response = client.post("/api/fuel-prices", json=overlap)
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Fuel price interval overlaps existing price."


def test_current_boundary_deactivation_and_validation_contract(api):
    client, factory, _ = api
    _, station_id, fuel_type_id = seed_pricing_data(factory)
    invalid = client.post(
        "/api/fuel-prices",
        json=price_payload(station_id, fuel_type_id, unit_price="0"),
    )
    assert invalid.status_code == 422
    assert client.post(
        "/api/fuel-prices",
        json=price_payload(
            station_id,
            fuel_type_id,
            effective_until=timestamp("2030-02-01T00:00:00"),
        ),
    ).status_code == 201
    second = client.post(
        "/api/fuel-prices",
        json=price_payload(
            station_id,
            fuel_type_id,
            unit_price="56",
            effective_from=timestamp("2030-02-01T00:00:00"),
        ),
    ).json()
    current = client.get(
        f"/api/stations/{station_id}/fuel-prices/{fuel_type_id}/current",
        params={"at": timestamp("2030-02-01T00:00:00")},
    )
    assert current.status_code == 200
    assert current.json()["id"] == second["id"]
    assert client.delete(f"/api/fuel-prices/{second['id']}").status_code == 204
    missing = client.get(
        f"/api/stations/{station_id}/fuel-prices/{fuel_type_id}/current",
        params={"at": timestamp("2030-02-01T00:00:00")},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "Fuel price not configured."


def test_price_preview_is_decimal_snapshot_and_does_not_write(api):
    client, factory, _ = api
    customer_id, station_id, fuel_type_id = seed_pricing_data(factory)
    created = client.post("/api/fuel-prices", json=price_payload(station_id, fuel_type_id))
    assert created.status_code == 201
    session = factory()
    before = session.get(FuelPrice, created.json()["id"])
    before_updated_at = before.updated_at
    session.close()

    response = client.post(
        "/api/fuel-prices/calculate-sale-price",
        json={
            "customer_id": customer_id,
            "station_id": station_id,
            "fuel_type_id": fuel_type_id,
            "quantity_liters": "40",
            "requested_at": timestamp("2030-01-01T00:00:00"),
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["list_unit_price"] == "55.0000"
    assert result["discount_amount_per_liter"] == "1.6500"
    assert result["applied_unit_price"] == "53.3500"
    assert result["total_amount"] == "2134.00"

    session = factory()
    after = session.get(FuelPrice, created.json()["id"])
    assert after.updated_at == before_updated_at
    assert session.query(FuelPrice).count() == 1
    session.close()


def test_started_price_cannot_be_rewritten(api):
    client, factory, _ = api
    _, station_id, fuel_type_id = seed_pricing_data(factory)
    session = factory()
    started = FuelPrice(
        station_id=station_id,
        fuel_type_id=fuel_type_id,
        unit_price=Decimal("50"),
        effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        is_active=True,
    )
    session.add(started)
    session.commit()
    price_id = started.id
    session.close()
    response = client.put(f"/api/fuel-prices/{price_id}", json={"unit_price": "51"})
    assert response.status_code == 400
    assert "cannot be rewritten" in response.json()["error"]["message"]


def test_fuel_price_change_creates_filtered_audit_snapshot(api):
    client, factory, admin = api
    _, station_id, fuel_type_id = seed_pricing_data(factory)
    created = client.post("/api/fuel-prices", json=price_payload(station_id, fuel_type_id))
    assert created.status_code == 201
    price_id = created.json()["id"]

    updated = client.put(f"/api/fuel-prices/{price_id}", json={"unit_price": "55.1000"})
    assert updated.status_code == 200
    rows = client.get(
        "/api/audit-logs",
        params={"entity_type": "FUEL_PRICE", "entity_id": price_id, "station_id": station_id, "action": "UPDATE"},
    )
    assert rows.status_code == 200
    audit = rows.json()[0]
    assert audit["user_id"] == admin.id
    assert audit["username_snapshot"] == "price-admin"
    assert audit["old_values_json"] == {"unit_price": "55.0000"}
    assert audit["new_values_json"] == {"unit_price": "55.1000"}

    session = factory()
    assert session.query(AuditLog).filter_by(entity_type="FUEL_PRICE").count() == 2
    session.close()


def test_audit_filters_redact_secrets_and_have_no_mutation_api(api):
    client, factory, admin = api
    session = factory()
    AuditService(session).record(
        action=AuditAction.UPDATE,
        entity_type="TEST_ENTITY",
        entity_id=77,
        user_id=admin.id,
        username=admin.username,
        new_values={"password_hash": "must-not-persist", "display_name": "Safe"},
    )
    session.commit()
    session.close()

    response = client.get(
        "/api/audit-logs",
        params={"user_id": admin.id, "entity_type": "TEST_ENTITY", "entity_id": 77, "action": "UPDATE", "created_from": "2020-01-01T00:00:00+00:00"},
    )
    assert response.status_code == 200
    assert response.json()[0]["new_values_json"] == {"display_name": "Safe"}
    assert client.put("/api/audit-logs").status_code == 405
    assert client.delete("/api/audit-logs").status_code == 405
