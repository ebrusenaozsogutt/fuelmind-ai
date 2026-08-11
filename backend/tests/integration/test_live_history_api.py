"""Acceptance coverage for the persisted live-history HTTP routes.

The fixture uses an in-memory SQLite database, so route tests exercise the
actual FastAPI dependency chain without reading or mutating development data.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import live
from app.api.dependencies import get_current_active_user, require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.fuel_type import FuelType
from app.models.pump import Pump
from app.models.sensor_reading import SensorReading
from app.models.station import Station
from app.models.tank import Tank
from app.utils.datetime_utils import utc_now
from app.utils.enums import PumpStatus, SourceType, UserRole

_LIVE_TABLES = [
    Station.__table__,
    FuelType.__table__,
    Tank.__table__,
    Pump.__table__,
    SensorReading.__table__,
]


@pytest.fixture
def live_api(monkeypatch: pytest.MonkeyPatch):
    """Provide seeded equipment and a real HTTP client on an isolated database."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_LIVE_TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(live, "SessionLocal", factory)
    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    session = factory()
    fuel = FuelType(name="Diesel", code="DSL")
    first = Station(code="S-1", name="First", city="A", district="A", address="A")
    second = Station(code="S-2", name="Second", city="B", district="B", address="B")
    empty = Station(code="S-3", name="Empty", city="C", district="C", address="C")
    session.add_all([fuel, first, second, empty])
    session.flush()
    tank_one = Tank(station_id=first.id, fuel_type_id=fuel.id, code="T-1", capacity_liters=1000, current_level_liters=500, minimum_safe_level=100, critical_level=50)
    tank_two = Tank(station_id=second.id, fuel_type_id=fuel.id, code="T-2", capacity_liters=1000, current_level_liters=500, minimum_safe_level=100, critical_level=50)
    session.add_all([tank_one, tank_two])
    session.flush()
    pump_one = Pump(station_id=first.id, tank_id=tank_one.id, code="P-1", status=PumpStatus.IDLE, nominal_flow_rate=10, minimum_flow_rate=1, maximum_motor_current=10, maximum_pressure=10)
    pump_two = Pump(station_id=second.id, tank_id=tank_two.id, code="P-2", status=PumpStatus.IDLE, nominal_flow_rate=10, minimum_flow_rate=1, maximum_motor_current=10, maximum_pressure=10)
    session.add_all([pump_one, pump_two])
    session.commit()
    data = {"session": session, "station": first, "other_station": second, "empty_station": empty, "tank": tank_one, "other_tank": tank_two, "pump": pump_one, "other_pump": pump_two}
    try:
        with TestClient(app) as client:
            yield client, data
    finally:
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(_LIVE_TABLES)))
        engine.dispose()


def _reading(data: dict[str, object], *, at, sequence: int, target: str = "both") -> SensorReading:
    station = data["station"] if target == "both" else data["other_station"]
    tank = data["tank"] if target == "both" else data["other_tank"]
    pump = data["pump"] if target == "both" else data["other_pump"]
    return SensorReading(
        station_id=station.id, tank_id=tank.id, pump_id=pump.id,
        simulation_run_id=77, sequence_number=sequence, reading_timestamp=at,
        tank_level=Decimal("420"), true_tank_level=Decimal("421"), temperature=Decimal("20"),
        water_level=Decimal("1"), flow_rate=Decimal("3"), pressure=Decimal("2"),
        motor_current=Decimal("4"), pump_temperature=Decimal("25"), error_count=0,
        working_duration=Decimal("1"), data_quality_score=Decimal("99"), source_type=SourceType.SIMULATION,
    )


def test_station_history_filters_orders_limits_and_preserves_contract(live_api) -> None:
    client, data = live_api
    now = utc_now()
    data["session"].add_all([
        _reading(data, at=now - timedelta(minutes=11), sequence=1),
        _reading(data, at=now - timedelta(minutes=5), sequence=2),
        _reading(data, at=now - timedelta(minutes=3), sequence=3),
        _reading(data, at=now - timedelta(minutes=1), sequence=4),
        _reading(data, at=now - timedelta(minutes=2), sequence=99, target="other"),
    ])
    data["session"].commit()
    response = client.get(f"/api/stations/{data['station'].id}/sensor-history")
    assert response.status_code == 200
    payload = response.json()
    assert [item["sequence_number"] for item in payload] == [2, 3, 4]
    assert payload[-1]["simulation_run_id"] == 77
    assert {"station_id", "tank_id", "pump_id", "reading_timestamp", "tank_level", "flow_rate"} <= payload[-1].keys()
    limited = client.get(f"/api/stations/{data['station'].id}/sensor-history?limit=2").json()
    assert [item["sequence_number"] for item in limited] == [3, 4]
    ranged = client.get(f"/api/stations/{data['station'].id}/sensor-history", params={"from": (now - timedelta(minutes=4)).isoformat(), "to": now.isoformat()})
    assert [item["sequence_number"] for item in ranged.json()] == [3, 4]


def test_tank_pump_history_empty_missing_and_validation(live_api) -> None:
    client, data = live_api
    now = utc_now()
    data["session"].add_all([_reading(data, at=now - timedelta(minutes=1), sequence=8), _reading(data, at=now - timedelta(minutes=1), sequence=9, target="other")])
    data["session"].commit()
    for path, expected in [(f"/api/tanks/{data['tank'].id}/sensor-history", [8]), (f"/api/pumps/{data['pump'].id}/sensor-history", [8])]:
        response = client.get(path, params={"limit": 1, "from": (now - timedelta(minutes=2)).isoformat(), "to": now.isoformat()})
        assert response.status_code == 200
        assert [item["sequence_number"] for item in response.json()] == expected
    assert client.get("/api/tanks/99999/sensor-history").status_code == 404
    assert client.get("/api/pumps/99999/sensor-history").status_code == 404
    assert client.get(f"/api/stations/{data['empty_station'].id}/sensor-history").json() == []
    for invalid in ("0", "-1", "5001"):
        assert client.get(f"/api/stations/{data['station'].id}/sensor-history?limit={invalid}").status_code == 422
    invalid_range = client.get(f"/api/stations/{data['station'].id}/sensor-history", params={"from": now.isoformat(), "to": (now - timedelta(minutes=1)).isoformat()})
    assert invalid_range.status_code == 400
    assert invalid_range.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


def test_live_status_uses_latest_station_readings_and_missing_station_is_404(live_api) -> None:
    client, data = live_api
    now = utc_now()
    assert client.get(f"/api/stations/{data['station'].id}/live-status").status_code == 200
    data["session"].add_all([_reading(data, at=now - timedelta(minutes=2), sequence=10), _reading(data, at=now - timedelta(minutes=1), sequence=11)])
    data["session"].commit()
    response = client.get(f"/api/stations/{data['station'].id}/live-status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_sequence"] == 11
    assert payload["tanks"][0]["station_id"] == data["station"].id
    assert payload["pumps"][0]["station_id"] == data["station"].id
    assert client.get("/api/stations/99999/live-status").status_code == 404


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.OPERATOR])
def test_history_allows_admin_and_operator(live_api, role: UserRole) -> None:
    client, data = live_api
    app.dependency_overrides.pop(require_operator_or_admin)
    app.dependency_overrides[get_current_active_user] = lambda: type(
        "User", (), {"role": role, "is_active": True}
    )()
    assert client.get(f"/api/stations/{data['station'].id}/sensor-history").status_code == 200
    app.dependency_overrides.pop(get_current_active_user)
    assert client.get(f"/api/stations/{data['station'].id}/sensor-history").status_code == 401
