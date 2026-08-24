"""HTTP acceptance coverage for explicit fault management."""

from datetime import datetime, timezone

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
from app.models.alarm import Alarm
from app.models.audit_log import AuditLog
from app.models.fault import Fault
from app.models.fuel_type import FuelType
from app.models.pump import Pump
from app.models.station import Station
from app.models.tank import Tank
from app.models.user import User
from app.utils.enums import AlarmSeverity, AlarmStatus, PumpStatus, UserRole


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_, __, **___):
    return "JSON"


TABLES = [
    User.__table__, Station.__table__, FuelType.__table__, Tank.__table__, Pump.__table__,
    Alarm.__table__, Fault.__table__, AuditLog.__table__,
]


@pytest.fixture
def fault_api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    user = User(username="fault-user", password_hash="x", full_name="Fault User", role=UserRole.OPERATOR)
    fuel = FuelType(name="Diesel", code="DSL")
    first = Station(code="F-1", name="First", city="Konya", district="A", address="A")
    second = Station(code="F-2", name="Second", city="Konya", district="B", address="B")
    session.add_all([user, fuel, first, second])
    session.flush()
    tanks = [
        Tank(station_id=station.id, fuel_type_id=fuel.id, code=f"T-{station.id}", capacity_liters=1000, current_level_liters=500, minimum_safe_level=100, critical_level=50, water_level=0)
        for station in (first, second)
    ]
    session.add_all(tanks)
    session.flush()
    pumps = [
        Pump(station_id=station.id, tank_id=tank.id, code=f"P-{station.id}", status=PumpStatus.IDLE, nominal_flow_rate=30, minimum_flow_rate=5, maximum_motor_current=10, maximum_pressure=5)
        for station, tank in zip((first, second), tanks, strict=True)
    ]
    session.add_all(pumps)
    session.flush()
    alarm = Alarm(station_id=first.id, pump_id=pumps[0].id, alarm_type="PUMP_ALERT", severity=AlarmSeverity.HIGH, title="Pump alert", status=AlarmStatus.NEW, detected_at=datetime(2026, 8, 18, 9, tzinfo=timezone.utc))
    false_alarm = Alarm(station_id=first.id, pump_id=pumps[0].id, alarm_type="FALSE", severity=AlarmSeverity.LOW, title="False alert", status=AlarmStatus.FALSE_POSITIVE, detected_at=datetime(2026, 8, 18, 10, tzinfo=timezone.utc))
    session.add_all([alarm, false_alarm])
    session.commit()
    ids = {"station": first.id, "other_station": second.id, "pump": pumps[0].id, "other_pump": pumps[1].id, "alarm": alarm.id, "false_alarm": false_alarm.id}
    session.close()
    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_operator_or_admin] = lambda: user
    app.dependency_overrides[require_admin] = lambda: user
    try:
        with TestClient(app) as client:
            yield client, ids
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(TABLES)))
        engine.dispose()


def payload(ids, *, code="PUMP_NOT_CONNECTED", alarm_id=None, target_id=None, station_id=None):
    return {
        "station_id": station_id or ids["station"], "alarm_id": alarm_id,
        "target_type": "PUMP", "target_id": target_id or ids["pump"],
        "fault_type": "CONNECTION", "fault_code": code, "title": "Pump connection issue",
        "description": "Pump cannot connect", "cause": "Communication timeout",
        "started_at": "2026-08-18T09:00:00+00:00", "detected_at": "2026-08-18T09:05:00+00:00",
    }


def test_accepts_required_codes_and_rejects_unknown_code(fault_api):
    client, ids = fault_api
    codes = ["INTERFACE_ERROR", "PUMP_NOT_CONNECTED", "USC_INITIALIZATION_ERROR", "PORT_COMMUNICATION_ERROR", "PROBE_COMMUNICATION_ERROR", "SENSOR_ERROR", "NOZZLE_ERROR"]
    for code in codes:
        response = client.post("/api/faults", json=payload(ids, code=code))
        assert response.status_code == 201
        assert response.json()["fault_code"] == code
        assert response.json()["cause"] == "Communication timeout"
    assert client.post("/api/faults", json=payload(ids, code="NOT_A_CODE")).status_code == 422


def test_alarm_link_target_rules_and_resolution_lifecycle(fault_api):
    client, ids = fault_api
    created = client.post("/api/faults", json=payload(ids, alarm_id=ids["alarm"]))
    assert created.status_code == 201
    fault = created.json()
    assert fault["alarm_id"] == ids["alarm"]
    assert client.post("/api/faults", json=payload(ids, alarm_id=ids["alarm"])).status_code == 400
    assert client.post("/api/faults", json=payload(ids, alarm_id=ids["false_alarm"])).status_code == 400
    assert client.post("/api/faults", json=payload(ids, target_id=9999)).status_code == 404
    assert client.post("/api/faults", json=payload(ids, target_id=ids["other_pump"])).status_code == 400
    investigating = client.patch(f"/api/faults/{fault['id']}/investigate")
    assert investigating.json()["status"] == "INVESTIGATING"
    resolved = client.patch(f"/api/faults/{fault['id']}/resolve", json={"resolution_note": "Cable reseated"})
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["resolved_by"] is not None
    assert resolved.json()["resolved_by_name"] == "Fault User"
    assert resolved.json()["resolution_note"] == "Cable reseated"
    assert resolved.json()["resolved_at"] is not None
    assert client.patch(f"/api/faults/{fault['id']}/resolve", json={"resolution_note": "Again"}).status_code == 400
    audits = client.get("/api/audit-logs", params={"entity_type": "FAULT", "entity_id": fault["id"], "action": "RESOLVE"})
    assert audits.status_code == 200
    audit = audits.json()[0]
    assert audit["user_id"] is not None
    assert audit["new_values_json"]["resolution_note"] == "Cable reseated"


def test_fault_filters(fault_api):
    client, ids = fault_api
    first = client.post("/api/faults", json=payload(ids, code="SENSOR_ERROR")).json()
    second = client.post("/api/faults", json=payload(ids, code="NOZZLE_ERROR")).json()
    assert client.get("/api/faults", params={"station_id": ids["station"], "fault_code": "SENSOR_ERROR"}).json()[0]["id"] == first["id"]
    assert client.get("/api/faults", params={"target_type": "PUMP", "target_id": ids["pump"], "status": "OPEN"}).status_code == 200
    assert client.get("/api/faults", params={"detected_from": "2026-08-18T09:00:00+00:00", "detected_to": "2026-08-18T10:00:00+00:00"}).status_code == 200
    assert client.get(f"/api/faults/{second['id']}").json()["fault_code"] == "NOZZLE_ERROR"
