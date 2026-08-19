"""Integration coverage for Stage 10 vehicle and driver management APIs."""

from datetime import date, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.commercial import (
    Customer,
    Driver,
    DriverVehicleAssignment,
    Fleet,
    FleetGroup,
    FuelCard,
    Vehicle,
)
from app.utils.datetime_utils import utc_now
from app.utils.enums import CardStatus, PaymentType


_TABLES = [
    Customer.__table__,
    Fleet.__table__,
    FleetGroup.__table__,
    Vehicle.__table__,
    Driver.__table__,
    DriverVehicleAssignment.__table__,
    FuelCard.__table__,
]


@pytest.fixture
def vehicle_driver_api():
    """Run the Prompt 3 management routes against isolated SQLite storage."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_admin] = lambda: object()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()


def _hierarchy(client: TestClient, *, code: str = "C-1") -> dict[str, object]:
    customer = client.post(
        "/api/customers",
        json={"code": code, "name": "Acme", "customer_type": "COMPANY"},
    ).json()
    fleet = client.post(
        "/api/fleets",
        json={"customer_id": customer["id"], "code": "F-1", "name": "Fleet"},
    ).json()
    group = client.post(
        "/api/fleet-groups",
        json={"fleet_id": fleet["id"], "code": "G-1", "name": "Group"},
    ).json()
    return {"customer": customer, "fleet": fleet, "group": group}


def _vehicle_payload(group_id: int, *, plate: str = "42 ABC 123") -> dict[str, object]:
    return {"fleet_group_id": group_id, "plate": plate, "brand": "Volvo"}


def _assignment_payload(
    driver_id: int, vehicle_id: int, start: date, end: date | None
) -> dict[str, object]:
    return {
        "driver_id": driver_id,
        "vehicle_id": vehicle_id,
        "assigned_from": start.isoformat(),
        "assigned_until": end.isoformat() if end else None,
        "status": "ACTIVE",
    }


def test_vehicle_crud_hierarchy_normalization_and_deactivation_guards(vehicle_driver_api) -> None:
    client, factory = vehicle_driver_api
    hierarchy = _hierarchy(client)
    group_id = hierarchy["group"]["id"]
    created = client.post("/api/vehicles", json=_vehicle_payload(group_id, plate=" 42 abc 123 "))
    assert created.status_code == 201
    vehicle = created.json()
    assert vehicle["plate"] == "42 ABC 123"
    assert client.post("/api/vehicles", json=_vehicle_payload(group_id)).status_code == 409
    assert client.post("/api/vehicles", json=_vehicle_payload(9999)).status_code == 404
    assert client.put(f"/api/vehicles/{vehicle['id']}", json={"brand": "Updated"}).json()["brand"] == "Updated"
    assert client.get("/api/vehicles", params={"search": "abc", "fleet_group_id": group_id}).json()[0]["id"] == vehicle["id"]
    assert client.get(f"/api/fleet-groups/{group_id}/vehicles").json()[0]["id"] == vehicle["id"]

    session = factory()
    session.add(
        FuelCard(
            vehicle_id=vehicle["id"],
            card_code="CARD-1",
            unit_id="UNIT-1",
            display_name="Vehicle card",
            valid_from=date.today(),
            payment_type=PaymentType.PREPAID,
            status=CardStatus.ACTIVE,
        )
    )
    session.commit()
    session.close()
    assert client.delete(f"/api/vehicles/{vehicle['id']}").status_code == 400

    safe = client.post("/api/vehicles", json=_vehicle_payload(group_id, plate="42 SAFE 1")).json()
    assert client.delete(f"/api/vehicles/{safe['id']}").status_code == 204

    def deny_admin() -> None:
        raise HTTPException(status_code=403, detail="Insufficient permissions.")

    app.dependency_overrides[require_admin] = deny_admin
    assert client.post("/api/vehicles", json=_vehicle_payload(group_id, plate="42 NOPE")).status_code == 403
    assert client.get(f"/api/vehicles/{vehicle['id']}").status_code == 200


def test_driver_crud_reference_rule_and_active_assignment_guard(vehicle_driver_api) -> None:
    client, _ = vehicle_driver_api
    first = client.post("/api/drivers", json={"full_name": " Ali Kaya ", "reference_code": " D-1 "})
    assert first.status_code == 201
    driver = first.json()
    assert driver["reference_code"] == "D-1"
    assert client.post("/api/drivers", json={"full_name": "Duplicate", "reference_code": "D-1"}).status_code == 409
    assert client.post("/api/drivers", json={"full_name": "Null one"}).status_code == 201
    assert client.post("/api/drivers", json={"full_name": "Null two"}).status_code == 201
    assert client.post("/api/drivers", json={"full_name": " "}).status_code == 422
    assert client.put(f"/api/drivers/{driver['id']}", json={"license_number": "LIC-1"}).json()["license_number"] == "LIC-1"
    assert client.get("/api/drivers", params={"search": "lic-1"}).json()[0]["id"] == driver["id"]

    hierarchy = _hierarchy(client)
    vehicle = client.post("/api/vehicles", json=_vehicle_payload(hierarchy["group"]["id"])).json()
    today = utc_now().date()
    assert client.post(
        "/api/driver-vehicle-assignments",
        json=_assignment_payload(driver["id"], vehicle["id"], today, None),
    ).status_code == 201
    assert client.delete(f"/api/drivers/{driver['id']}").status_code == 400


def test_assignment_overlap_boundary_lifecycle_lists_and_current_driver(vehicle_driver_api) -> None:
    client, _ = vehicle_driver_api
    hierarchy = _hierarchy(client)
    group_id = hierarchy["group"]["id"]
    first_vehicle = client.post("/api/vehicles", json=_vehicle_payload(group_id)).json()
    second_vehicle = client.post("/api/vehicles", json=_vehicle_payload(group_id, plate="42 XYZ 456")).json()
    first_driver = client.post("/api/drivers", json={"full_name": "Ali"}).json()
    second_driver = client.post("/api/drivers", json={"full_name": "Veli"}).json()
    start = date(2026, 1, 1)
    end = start + timedelta(days=10)
    assignment = client.post(
        "/api/driver-vehicle-assignments",
        json=_assignment_payload(first_driver["id"], first_vehicle["id"], start, end),
    )
    assert assignment.status_code == 201
    assignment_id = assignment.json()["id"]
    assert client.post(
        "/api/driver-vehicle-assignments",
        json=_assignment_payload(second_driver["id"], first_vehicle["id"], start + timedelta(days=5), end + timedelta(days=5)),
    ).status_code == 400
    assert client.post(
        "/api/driver-vehicle-assignments",
        json=_assignment_payload(first_driver["id"], second_vehicle["id"], start + timedelta(days=5), end),
    ).status_code == 400
    assert client.post(
        "/api/driver-vehicle-assignments",
        json=_assignment_payload(second_driver["id"], first_vehicle["id"], end, end + timedelta(days=5)),
    ).status_code == 201
    assert client.put(
        f"/api/driver-vehicle-assignments/{assignment_id}",
        json={"assigned_until": end.isoformat()},
    ).status_code == 200
    assert len(client.get(f"/api/vehicles/{first_vehicle['id']}/driver-assignments").json()) == 2
    assert len(client.get(f"/api/drivers/{first_driver['id']}/vehicle-assignments").json()) == 1
    assert client.delete(f"/api/driver-vehicle-assignments/{assignment_id}").status_code == 204

    today = utc_now().date()
    current = client.post(
        "/api/driver-vehicle-assignments",
        json=_assignment_payload(first_driver["id"], second_vehicle["id"], today, None),
    )
    assert current.status_code == 201
    assert client.get(f"/api/vehicles/{second_vehicle['id']}/current-driver").json()["id"] == first_driver["id"]
    assert client.get(f"/api/vehicles/{first_vehicle['id']}/current-driver").json() is None
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/api/vehicles",
        "/api/drivers",
        "/api/driver-vehicle-assignments",
        "/api/fleet-groups/{fleet_group_id}/vehicles",
        "/api/vehicles/{vehicle_id}/driver-assignments",
        "/api/drivers/{driver_id}/vehicle-assignments",
        "/api/vehicles/{vehicle_id}/current-driver",
    } <= paths.keys()
