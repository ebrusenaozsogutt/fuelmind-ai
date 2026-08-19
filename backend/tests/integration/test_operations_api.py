"""HTTP acceptance coverage for Stage 11 Prompt 1 station operations."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.fuel_type import FuelType
from app.models.audit_log import AuditLog
from app.models.commercial import Customer, Fleet, FleetGroup, FuelCard, Vehicle
from app.models.operations import Attendant, AttendantShiftAssignment, Shift
from app.models.nozzle import Nozzle
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.station import Station
from app.models.tank import Tank
from app.utils.enums import PumpStatus, SaleStatus, SensorStatus


TABLES = [
    Station.__table__,
    FuelType.__table__,
    Tank.__table__,
    Pump.__table__,
    Nozzle.__table__,
    Attendant.__table__,
    Shift.__table__,
    AttendantShiftAssignment.__table__,
    Sale.__table__,
    AuditLog.__table__,
    Customer.__table__,
    Fleet.__table__,
    FleetGroup.__table__,
    Vehicle.__table__,
    FuelCard.__table__,
]


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_, __, **___):
    return "JSON"


@pytest.fixture
def operations_api():
    """Run operations and sale endpoints through HTTP against isolated storage."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    fuel = FuelType(name="Diesel", code="DSL")
    primary = Station(
        code="OPS-1",
        name="Operations One",
        city="Konya",
        district="Selçuklu",
        address="Test Address",
    )
    secondary = Station(
        code="OPS-2",
        name="Operations Two",
        city="Konya",
        district="Meram",
        address="Other Test Address",
    )
    session.add_all([fuel, primary, secondary])
    session.flush()
    tank = Tank(
        station_id=primary.id,
        fuel_type_id=fuel.id,
        code="OPS-TANK-1",
        capacity_liters=Decimal("10000"),
        current_level_liters=Decimal("9000"),
        minimum_safe_level=Decimal("1000"),
        critical_level=Decimal("500"),
        water_level=Decimal("0"),
        sensor_status=SensorStatus.ACTIVE,
    )
    session.add(tank)
    session.flush()
    pump = Pump(
        station_id=primary.id,
        tank_id=tank.id,
        code="OPS-PUMP-1",
        status=PumpStatus.ACTIVE,
        nominal_flow_rate=Decimal("45"),
        minimum_flow_rate=Decimal("10"),
        maximum_motor_current=Decimal("18"),
        maximum_pressure=Decimal("8"),
        total_working_hours=Decimal("0"),
    )
    session.add(pump)
    session.commit()
    ids = {"primary": primary.id, "secondary": secondary.id, "fuel": fuel.id,
           "tank": tank.id, "pump": pump.id}
    session.close()
    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_admin] = lambda: object()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    try:
        with TestClient(app) as client:
            yield client, factory, ids
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(TABLES)))
        engine.dispose()


def attendant_payload(station_id: int, code: str, employee_number: str) -> dict[str, object]:
    return {
        "station_id": station_id,
        "code": code,
        "full_name": f"{code} Attendant",
        "employee_number": employee_number,
    }


def shift_payload(station_id: int, code: str, start: str = "08:00", end: str = "16:00") -> dict[str, object]:
    return {
        "station_id": station_id,
        "code": code,
        "name": f"{code} Shift",
        "start_time": start,
        "end_time": end,
    }


def sale_payload(ids: dict[str, int], **operations: int | None) -> dict[str, object]:
    return {
        "station_id": ids["primary"],
        "tank_id": ids["tank"],
        "pump_id": ids["pump"],
        "fuel_type_id": ids["fuel"],
        "sale_timestamp": "2030-01-01T10:00:00+00:00",
        "quantity_liters": "10",
        "unit_price": "55",
        "duration_seconds": 60,
        **operations,
    }


def create_attendant(client: TestClient, station_id: int, code: str, employee_number: str) -> int:
    response = client.post("/api/attendants", json=attendant_payload(station_id, code, employee_number))
    assert response.status_code == 201
    return response.json()["id"]


def create_shift(client: TestClient, station_id: int, code: str) -> int:
    response = client.post("/api/shifts", json=shift_payload(station_id, code))
    assert response.status_code == 201
    return response.json()["id"]


def create_assignment(client: TestClient, attendant_id: int, shift_id: int) -> int:
    response = client.post(
        "/api/attendant-shift-assignments",
        json={"attendant_id": attendant_id, "shift_id": shift_id},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_attendant_crud_and_duplicate_code_rejection(operations_api) -> None:
    client, _, ids = operations_api
    created = client.post(
        "/api/attendants", json=attendant_payload(ids["primary"], "ops-att", "EMP-OPS-1")
    )
    assert created.status_code == 201
    attendant = created.json()
    assert attendant["code"] == "OPS-ATT"
    assert client.get("/api/attendants", params={"station_id": ids["primary"]}).json()[0]["id"] == attendant["id"]
    assert client.get(f"/api/attendants/{attendant['id']}").status_code == 200
    updated = client.put(f"/api/attendants/{attendant['id']}", json={"full_name": "Updated Attendant"})
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "UPDATED ATTENDANT"
    duplicate = client.post(
        "/api/attendants", json=attendant_payload(ids["primary"], "OPS-ATT", "EMP-OPS-2")
    )
    assert duplicate.status_code == 409
    assert client.delete(f"/api/attendants/{attendant['id']}").status_code == 204
    assert client.get(f"/api/attendants/{attendant['id']}").json()["is_active"] is False


def test_shift_crud_supports_overnight_and_rejects_equal_times(operations_api) -> None:
    client, _, ids = operations_api
    morning = client.post("/api/shifts", json=shift_payload(ids["primary"], "MORNING"))
    overnight = client.post(
        "/api/shifts", json=shift_payload(ids["primary"], "OVERNIGHT", "22:00", "06:00")
    )
    midnight = client.post(
        "/api/shifts", json=shift_payload(ids["primary"], "MIDNIGHT", "00:00", "08:00")
    )
    assert morning.status_code == overnight.status_code == midnight.status_code == 201
    shift_id = morning.json()["id"]
    listed = client.get("/api/shifts", params={"station_id": ids["primary"]})
    assert listed.status_code == 200
    assert {item["code"] for item in listed.json()} == {"MORNING", "OVERNIGHT", "MIDNIGHT"}
    assert client.get(f"/api/shifts/{shift_id}").status_code == 200
    assert client.put(f"/api/shifts/{shift_id}", json={"name": "Updated Morning"}).json()["name"] == "Updated Morning"
    invalid = client.post(
        "/api/shifts", json=shift_payload(ids["primary"], "INVALID", "08:00", "08:00")
    )
    assert invalid.status_code == 422
    assert client.put(f"/api/shifts/{shift_id}", json={"start_time": "16:00"}).status_code == 400
    assert client.delete(f"/api/shifts/{shift_id}").status_code == 204
    assert client.get(f"/api/shifts/{shift_id}").json()["is_active"] is False


def test_assignment_and_sale_business_rules(operations_api) -> None:
    client, factory, ids = operations_api
    attendant_id = create_attendant(client, ids["primary"], "A-VALID", "EMP-VALID")
    shift_id = create_shift(client, ids["primary"], "S-VALID")
    assignment_id = create_assignment(client, attendant_id, shift_id)
    valid = client.post(
        "/api/sales", json=sale_payload(ids, attendant_id=attendant_id, shift_id=shift_id)
    )
    assert valid.status_code == 201
    assert valid.json()["attendant_id"] == attendant_id
    assert valid.json()["shift_id"] == shift_id
    assert valid.json()["attendant_name"] is not None
    assert valid.json()["shift_name"] is not None
    session = factory()
    stored = session.get(Sale, valid.json()["id"])
    assert stored.attendant_id == attendant_id
    assert stored.shift_id == shift_id
    session.close()

    other_attendant = create_attendant(client, ids["secondary"], "A-OTHER", "EMP-OTHER")
    other_shift = create_shift(client, ids["secondary"], "S-OTHER")
    assert client.post(
        "/api/attendant-shift-assignments",
        json={"attendant_id": attendant_id, "shift_id": other_shift},
    ).status_code == 400
    assert client.post(
        "/api/sales", json=sale_payload(ids, attendant_id=other_attendant, shift_id=shift_id)
    ).status_code == 400
    assert client.post(
        "/api/sales", json=sale_payload(ids, attendant_id=attendant_id, shift_id=other_shift)
    ).status_code == 400

    unassigned_attendant = create_attendant(client, ids["primary"], "A-NO-ASSIGN", "EMP-NO-ASSIGN")
    assert client.post(
        "/api/sales", json=sale_payload(ids, attendant_id=unassigned_attendant, shift_id=shift_id)
    ).status_code == 400

    assert client.delete(f"/api/attendants/{attendant_id}").status_code == 204
    assert client.post(
        "/api/sales", json=sale_payload(ids, attendant_id=attendant_id, shift_id=shift_id)
    ).status_code == 400

    inactive_shift_attendant = create_attendant(client, ids["primary"], "A-INACTIVE-S", "EMP-INACTIVE-S")
    inactive_shift_id = create_shift(client, ids["primary"], "S-INACTIVE")
    create_assignment(client, inactive_shift_attendant, inactive_shift_id)
    assert client.delete(f"/api/shifts/{inactive_shift_id}").status_code == 204
    assert client.post(
        "/api/sales",
        json=sale_payload(ids, attendant_id=inactive_shift_attendant, shift_id=inactive_shift_id),
    ).status_code == 400

    assignment_attendant = create_attendant(client, ids["primary"], "A-INACTIVE-A", "EMP-INACTIVE-A")
    assignment_shift = create_shift(client, ids["primary"], "S-INACTIVE-A")
    inactive_assignment_id = create_assignment(client, assignment_attendant, assignment_shift)
    session = factory()
    assignment = session.get(AttendantShiftAssignment, inactive_assignment_id)
    assignment.is_active = False
    session.commit()
    session.close()
    assert client.post(
        "/api/sales",
        json=sale_payload(ids, attendant_id=assignment_attendant, shift_id=assignment_shift),
    ).status_code == 400

    legacy = client.post("/api/sales", json=sale_payload(ids))
    assert legacy.status_code == 201
    session = factory()
    persisted_legacy = session.scalar(select(Sale).where(Sale.id == legacy.json()["id"]))
    assert persisted_legacy.attendant_id is None
    assert persisted_legacy.shift_id is None
    session.close()
    assert assignment_id > 0


def test_attendant_status_and_shift_change_create_audit(operations_api) -> None:
    client, factory, ids = operations_api
    attendant_id = create_attendant(client, ids["primary"], "A-AUDIT", "EMP-AUDIT")
    shift_id = create_shift(client, ids["primary"], "S-AUDIT")

    assert client.put(
        f"/api/attendants/{attendant_id}", json={"is_active": False}
    ).status_code == 200
    assert client.put(
        f"/api/shifts/{shift_id}", json={"name": "Audited Shift"}
    ).status_code == 200

    session = factory()
    attendant_audit = session.query(AuditLog).filter_by(
        entity_type="ATTENDANT", entity_id=attendant_id
    ).one()
    shift_audit = session.query(AuditLog).filter_by(
        entity_type="SHIFT", entity_id=shift_id
    ).one()
    assert attendant_audit.old_values_json == {"is_active": True}
    assert attendant_audit.new_values_json == {"is_active": False}
    assert shift_audit.old_values_json == {"name": "S-AUDIT Shift"}
    assert shift_audit.new_values_json == {"name": "Audited Shift"}
    session.close()


def test_persisted_sale_reports_apply_combined_filters_and_exclude_cancelled(operations_api) -> None:
    client, factory, ids = operations_api
    attendant_id = create_attendant(client, ids["primary"], "A-REPORT", "EMP-REPORT")
    shift_id = create_shift(client, ids["primary"], "S-REPORT")
    create_assignment(client, attendant_id, shift_id)
    completed = client.post(
        "/api/sales", json=sale_payload(ids, attendant_id=attendant_id, shift_id=shift_id)
    ).json()
    cancelled = client.post(
        "/api/sales", json=sale_payload(ids, attendant_id=attendant_id, shift_id=shift_id)
    ).json()
    session = factory()
    session.get(Sale, cancelled["id"]).sale_status = SaleStatus.CANCELLED
    session.commit()
    session.close()

    params = {"station_id": ids["primary"], "pump_id": ids["pump"], "fuel_type_id": ids["fuel"], "date_from": "2030-01-01", "date_to": "2030-01-01", "attendant_id": attendant_id, "shift_id": shift_id}
    rows = client.get("/api/reports/sales", params=params)
    assert rows.status_code == 200
    assert {row["sale_id"] for row in rows.json()} == {completed["id"], cancelled["id"]}
    end_of_day = client.get("/api/reports/end-of-day", params=params)
    assert end_of_day.status_code == 200
    assert end_of_day.json()["transaction_count"] == 1
    assert client.get("/api/reports/attendants", params=params).json()[0]["transaction_count"] == 1
    csv_export = client.get("/api/reports/sales/export/csv", params=params)
    assert csv_export.status_code == 200
    assert csv_export.headers["content-type"].startswith("text/csv")
    assert csv_export.content.decode("utf-8-sig").splitlines()[0].startswith("sale_id,")
    assert len(csv_export.content.decode("utf-8-sig").splitlines()) - 1 == len(rows.json())
    pdf_export = client.get("/api/reports/sales/export/pdf", params=params)
    assert pdf_export.status_code == 200
    assert pdf_export.headers["content-type"] == "application/pdf"
    assert pdf_export.content.startswith(b"%PDF-")
