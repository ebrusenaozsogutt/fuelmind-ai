"""Integration coverage for Stage 10 customer and fleet management APIs."""

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
    CustomerAuthorizedPerson,
    Fleet,
    FleetGroup,
    Vehicle,
)


_TABLES = [
    Customer.__table__,
    CustomerAuthorizedPerson.__table__,
    Fleet.__table__,
    FleetGroup.__table__,
    Vehicle.__table__,
]


@pytest.fixture
def commercial_api():
    """Run commercial management endpoints against isolated SQLite storage."""

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


def _customer_payload(*, code: str = "C-1", customer_type: str = "COMPANY") -> dict[str, object]:
    return {
        "code": code,
        "name": "Acme Logistics",
        "customer_type": customer_type,
        "sector": "LOJISTIK",
        "discount_rate": "5.5",
        "request_status": "PENDING",
    }


def _fleet_payload(customer_id: int, *, code: str = "KONYA") -> dict[str, object]:
    return {"customer_id": customer_id, "code": code, "name": "Konya Fleet"}


def _group_payload(fleet_id: int, *, code: str = "HEAVY") -> dict[str, object]:
    return {"fleet_id": fleet_id, "code": code, "name": "Heavy Vehicles"}


def test_customer_crud_filters_authorization_and_openapi(commercial_api) -> None:
    client, _ = commercial_api
    company = client.post("/api/customers", json=_customer_payload())
    individual = client.post(
        "/api/customers", json=_customer_payload(code="C-2", customer_type="INDIVIDUAL")
    )
    assert company.status_code == 201
    assert individual.status_code == 201
    customer = company.json()
    assert customer["customer_type"] == "COMPANY"
    assert client.post("/api/customers", json=_customer_payload()).status_code == 409
    assert client.post(
        "/api/customers", json={**_customer_payload(code="C-0"), "discount_rate": "0"}
    ).status_code == 201
    assert client.post(
        "/api/customers", json={**_customer_payload(code="C-N"), "discount_rate": "-0.01"}
    ).status_code == 422
    assert client.post(
        "/api/customers", json={**_customer_payload(code="C-3"), "discount_rate": "101"}
    ).status_code == 422
    assert client.put(
        f"/api/customers/{customer['id']}",
        json={"name": "Updated", "request_status": "APPROVED", "discount_rate": "100"},
    ).json()["request_status"] == "APPROVED"
    assert client.get("/api/customers", params={"search": "updated"}).json()[0]["id"] == customer["id"]
    assert client.get("/api/customers", params={"customer_type": "INDIVIDUAL"}).json()[0]["id"] == individual.json()["id"]
    assert client.delete(f"/api/customers/{customer['id']}").status_code == 204
    assert client.get(f"/api/customers/{customer['id']}").json()["is_active"] is False

    def deny_admin() -> None:
        raise HTTPException(status_code=403, detail="Insufficient permissions.")

    app.dependency_overrides[require_admin] = deny_admin
    assert client.post("/api/customers", json=_customer_payload(code="NOPE")).status_code == 403
    assert client.get("/api/customers").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/customers", "/api/customer-authorized-persons", "/api/fleets", "/api/fleet-groups"} <= paths.keys()


def test_authorized_person_primary_rule_nested_list_and_deactivate(commercial_api) -> None:
    client, _ = commercial_api
    customer = client.post("/api/customers", json=_customer_payload()).json()
    first = client.post(
        "/api/customer-authorized-persons",
        json={"customer_id": customer["id"], "full_name": "First Contact", "is_primary": True},
    )
    assert first.status_code == 201
    assert client.post(
        "/api/customer-authorized-persons",
        json={"customer_id": customer["id"], "full_name": "Second Primary", "is_primary": True},
    ).status_code == 400
    assert client.post(
        "/api/customer-authorized-persons",
        json={"customer_id": customer["id"], "full_name": "Second Contact"},
    ).status_code == 201
    assert client.post(
        "/api/customer-authorized-persons",
        json={"customer_id": 9999, "full_name": "Missing"},
    ).status_code == 404
    nested = client.get(f"/api/customers/{customer['id']}/authorized-persons")
    assert len(nested.json()) == 2
    detail = client.get(f"/api/customers/{customer['id']}/detail").json()
    assert detail["customer"]["id"] == customer["id"]
    assert len(detail["authorized_persons"]) == 2
    assert client.delete(f"/api/customer-authorized-persons/{first.json()['id']}").status_code == 204


def test_fleet_rules_lists_updates_and_safe_deactivate(commercial_api) -> None:
    client, _ = commercial_api
    active_customer = client.post("/api/customers", json=_customer_payload()).json()
    inactive_customer = client.post(
        "/api/customers", json={**_customer_payload(code="C-2"), "is_active": False}
    ).json()
    fleet = client.post("/api/fleets", json=_fleet_payload(active_customer["id"]))
    assert fleet.status_code == 201
    fleet_id = fleet.json()["id"]
    assert client.post("/api/fleets", json=_fleet_payload(active_customer["id"])).status_code == 409
    assert client.post("/api/fleets", json=_fleet_payload(9999, code="MISSING")).status_code == 404
    assert client.post("/api/fleets", json=_fleet_payload(inactive_customer["id"])).status_code == 400
    assert client.post("/api/fleets", json=_fleet_payload(inactive_customer["id"], code="PASSIVE",) | {"is_active": False}).status_code == 201
    other_customer = client.post("/api/customers", json=_customer_payload(code="C-3")).json()
    assert client.post("/api/fleets", json=_fleet_payload(other_customer["id"])).status_code == 201
    assert client.put(f"/api/fleets/{fleet_id}", json={"request_status": "APPROVED"}).json()["request_status"] == "APPROVED"
    assert len(client.get(f"/api/customers/{active_customer['id']}/fleets").json()) == 1
    group = client.post("/api/fleet-groups", json=_group_payload(fleet_id))
    assert group.status_code == 201
    assert client.delete(f"/api/fleets/{fleet_id}").status_code == 400


def test_fleet_group_rules_lists_updates_and_active_vehicle_guard(commercial_api) -> None:
    client, factory = commercial_api
    customer = client.post("/api/customers", json=_customer_payload()).json()
    fleet = client.post("/api/fleets", json=_fleet_payload(customer["id"])).json()
    group = client.post("/api/fleet-groups", json=_group_payload(fleet["id"]))
    assert group.status_code == 201
    group_id = group.json()["id"]
    assert client.post("/api/fleet-groups", json=_group_payload(fleet["id"])).status_code == 409
    assert client.post("/api/fleet-groups", json=_group_payload(9999, code="MISSING")).status_code == 404
    assert client.put(f"/api/fleet-groups/{group_id}", json={"name": "Updated Group"}).json()["name"] == "Updated Group"
    assert len(client.get(f"/api/fleets/{fleet['id']}/groups").json()) == 1
    session = factory()
    session.add(Vehicle(fleet_group_id=group_id, plate="42ABC42"))
    session.commit()
    session.close()
    assert client.delete(f"/api/fleet-groups/{group_id}").status_code == 400

    inactive_fleet = client.post(
        "/api/fleets", json={**_fleet_payload(customer["id"], code="PASSIVE"), "is_active": False}
    ).json()
    assert client.post("/api/fleet-groups", json=_group_payload(inactive_fleet["id"])).status_code == 400
    assert client.post(
        "/api/fleet-groups",
        json={**_group_payload(inactive_fleet["id"], code="INACTIVE"), "is_active": False},
    ).status_code == 201
    other_fleet = client.post(
        "/api/fleets", json=_fleet_payload(customer["id"], code="OTHER")
    ).json()
    assert client.post(
        "/api/fleet-groups", json=_group_payload(other_fleet["id"])
    ).status_code == 201
