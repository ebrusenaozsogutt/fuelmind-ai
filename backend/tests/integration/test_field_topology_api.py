"""API acceptance coverage for Stage 9 field-device topology management."""

from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.communication_port import CommunicationPort
from app.models.device_controller import DeviceController
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.probe_reading import ProbeReading
from app.models.pump import Pump
from app.models.station import Station
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.utils.enums import PumpStatus


_TABLES = [
    Station.__table__,
    FuelType.__table__,
    DeviceController.__table__,
    CommunicationPort.__table__,
    Tank.__table__,
    Pump.__table__,
    TankProbe.__table__,
    ProbeReading.__table__,
    Nozzle.__table__,
]


@pytest.fixture
def topology_api():
    """Run topology management routes against isolated SQLite storage."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    first = Station(
        code="S-1", name="First", city="Istanbul", district="Kadikoy", address="A"
    )
    second = Station(
        code="S-2", name="Second", city="Ankara", district="Cankaya", address="B"
    )
    diesel = FuelType(name="Diesel", code="DSL")
    gasoline = FuelType(name="Gasoline", code="GAS")
    session.add_all([first, second, diesel, gasoline])
    session.flush()
    tank = Tank(
        station_id=first.id,
        fuel_type_id=diesel.id,
        code="T-1",
        capacity_liters=Decimal("1000"),
        current_level_liters=Decimal("500"),
        minimum_safe_level=Decimal("100"),
        critical_level=Decimal("50"),
    )
    other_tank = Tank(
        station_id=second.id,
        fuel_type_id=diesel.id,
        code="T-2",
        capacity_liters=Decimal("1000"),
        current_level_liters=Decimal("500"),
        minimum_safe_level=Decimal("100"),
        critical_level=Decimal("50"),
    )
    session.add_all([tank, other_tank])
    session.flush()
    pump = Pump(
        station_id=first.id,
        tank_id=tank.id,
        code="P-1",
        status=PumpStatus.IDLE,
        nominal_flow_rate=Decimal("10"),
        minimum_flow_rate=Decimal("1"),
        maximum_motor_current=Decimal("10"),
        maximum_pressure=Decimal("10"),
    )
    second_pump = Pump(
        station_id=first.id,
        tank_id=tank.id,
        code="P-2",
        status=PumpStatus.IDLE,
        nominal_flow_rate=Decimal("10"),
        minimum_flow_rate=Decimal("1"),
        maximum_motor_current=Decimal("10"),
        maximum_pressure=Decimal("10"),
    )
    session.add_all([pump, second_pump])
    session.commit()
    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_admin] = lambda: object()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    try:
        with TestClient(app) as client:
            yield client, {
                "station": first,
                "other_station": second,
                "fuel": diesel,
                "other_fuel": gasoline,
                "tank": tank,
                "other_tank": other_tank,
                "pump": pump,
                "second_pump": second_pump,
            }
    finally:
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()


def _controller_payload(station_id: int, *, code: str = "CTRL-1") -> dict[str, object]:
    return {
        "station_id": station_id,
        "code": code,
        "name": "Forecourt Controller",
        "controller_type": "GENERIC",
        "status": "ONLINE",
    }


def _port_payload(
    controller_id: int, *, port_number: int, port_type: str = "PUMP"
) -> dict[str, object]:
    return {
        "controller_id": controller_id,
        "port_number": port_number,
        "name": f"Port {port_number}",
        "port_type": port_type,
        "status": "ONLINE",
        "baud_rate": 9600,
    }


def test_controller_and_port_crud_rules(topology_api) -> None:
    client, data = topology_api
    station_id = data["station"].id
    other_station_id = data["other_station"].id
    created = client.post("/api/device-controllers", json=_controller_payload(station_id))
    assert created.status_code == 201
    controller = created.json()
    assert controller["code"] == "CTRL-1"
    assert client.post(
        "/api/device-controllers", json=_controller_payload(station_id)
    ).status_code == 409
    assert client.post(
        "/api/device-controllers", json=_controller_payload(other_station_id)
    ).status_code == 201
    assert client.post(
        "/api/device-controllers", json=_controller_payload(9999, code="MISSING")
    ).status_code == 404
    assert client.put(
        f"/api/device-controllers/{controller['id']}", json={"name": "Updated"}
    ).json()["name"] == "Updated"
    assert len(client.get(f"/api/stations/{station_id}/device-controllers").json()) == 1

    port = client.post(
        "/api/communication-ports",
        json=_port_payload(controller["id"], port_number=1),
    )
    assert port.status_code == 201
    assert port.json()["controller_code"] == "CTRL-1"
    assert client.post(
        "/api/communication-ports",
        json=_port_payload(controller["id"], port_number=1),
    ).status_code == 409
    other_controller = client.post(
        "/api/device-controllers", json=_controller_payload(station_id, code="CTRL-2")
    ).json()
    assert client.post(
        "/api/communication-ports",
        json=_port_payload(other_controller["id"], port_number=1),
    ).status_code == 201
    assert client.post(
        "/api/communication-ports",
        json=_port_payload(9999, port_number=2),
    ).status_code == 404
    assert client.post(
        "/api/communication-ports",
        json={**_port_payload(controller["id"], port_number=2), "baud_rate": 0},
    ).status_code == 422
    assert len(client.get(f"/api/device-controllers/{controller['id']}/ports").json()) == 1
    assert client.delete(f"/api/device-controllers/{controller['id']}").status_code == 204


def test_pump_port_topology_rules_and_safe_port_delete(topology_api) -> None:
    client, data = topology_api
    controller = client.post(
        "/api/device-controllers", json=_controller_payload(data["station"].id)
    ).json()
    pump_port = client.post(
        "/api/communication-ports",
        json=_port_payload(controller["id"], port_number=1),
    ).json()
    probe_port = client.post(
        "/api/communication-ports",
        json=_port_payload(controller["id"], port_number=2, port_type="PROBE"),
    ).json()
    pump_id = data["pump"].id
    linked = client.put(
        f"/api/pumps/{pump_id}",
        json={"communication_port_id": pump_port["id"], "device_address": "PUMP-1"},
    )
    assert linked.status_code == 200
    assert linked.json()["communication_port_id"] == pump_port["id"]
    assert client.put(
        f"/api/pumps/{pump_id}", json={"communication_port_id": probe_port["id"]}
    ).status_code == 400
    other_controller = client.post(
        "/api/device-controllers",
        json=_controller_payload(data["other_station"].id, code="OTHER"),
    ).json()
    foreign_port = client.post(
        "/api/communication-ports",
        json=_port_payload(other_controller["id"], port_number=1),
    ).json()
    assert client.put(
        f"/api/pumps/{pump_id}", json={"communication_port_id": foreign_port["id"]}
    ).status_code == 400
    assert client.put(
        f"/api/pumps/{data['second_pump'].id}",
        json={"communication_port_id": pump_port["id"], "device_address": "PUMP-1"},
    ).status_code == 409
    assert client.delete(f"/api/communication-ports/{pump_port['id']}").status_code == 400


def test_tank_probe_rules_and_read_only_history(topology_api) -> None:
    client, data = topology_api
    controller = client.post(
        "/api/device-controllers", json=_controller_payload(data["station"].id)
    ).json()
    probe_port = client.post(
        "/api/communication-ports",
        json=_port_payload(controller["id"], port_number=1, port_type="PROBE"),
    ).json()
    pump_port = client.post(
        "/api/communication-ports",
        json=_port_payload(controller["id"], port_number=2),
    ).json()
    payload = {
        "tank_id": data["tank"].id,
        "communication_port_id": probe_port["id"],
        "code": "PRB-1",
        "name": "Tank Probe",
        "status": "ONLINE",
    }
    created = client.post("/api/tank-probes", json=payload)
    assert created.status_code == 201
    probe = created.json()
    assert client.get(f"/api/tanks/{data['tank'].id}/probe").json()["id"] == probe["id"]
    assert client.get(f"/api/tank-probes/{probe['id']}/readings").json() == []
    assert client.post(
        "/api/tank-probes", json={**payload, "code": "PRB-2"}
    ).status_code == 400
    assert client.put(f"/api/tank-probes/{probe['id']}", json={"is_active": False}).status_code == 200
    replacement = client.post(
        "/api/tank-probes", json={**payload, "code": "PRB-2"}
    )
    assert replacement.status_code == 201
    assert client.put(
        f"/api/tank-probes/{replacement.json()['id']}",
        json={"communication_port_id": pump_port["id"]},
    ).status_code == 400
    assert client.post(
        "/api/tank-probes",
        json={
            "tank_id": data["other_tank"].id,
            "communication_port_id": probe_port["id"],
            "code": "FOREIGN",
            "name": "Foreign Probe",
        },
    ).status_code == 400
    assert client.post(
        "/api/tank-probes",
        json={
            "tank_id": data["other_tank"].id,
            "code": "SIM-1",
            "name": "Simulation Probe",
        },
    ).status_code == 201


def test_nozzle_rules_and_pump_nozzle_list(topology_api) -> None:
    client, data = topology_api
    payload = {
        "pump_id": data["pump"].id,
        "fuel_type_id": data["fuel"].id,
        "code": "N-1",
        "nozzle_number": 1,
        "totalizer_liters": "100",
    }
    created = client.post("/api/nozzles", json=payload)
    assert created.status_code == 201
    nozzle = created.json()
    assert nozzle["pump_code"] == "P-1"
    assert nozzle["fuel_type_code"] == "DSL"
    assert client.post("/api/nozzles", json=payload).status_code == 409
    assert client.post(
        "/api/nozzles", json={**payload, "code": "N-2", "nozzle_number": 2}
    ).status_code == 201
    assert client.post(
        "/api/nozzles",
        json={**payload, "code": "BAD", "nozzle_number": 3, "totalizer_liters": "-1"},
    ).status_code == 422
    assert client.post(
        "/api/nozzles",
        json={**payload, "code": "FUEL", "nozzle_number": 3, "fuel_type_id": data["other_fuel"].id},
    ).status_code == 400
    assert client.put(
        f"/api/nozzles/{nozzle['id']}", json={"totalizer_liters": "101"}
    ).status_code == 200
    assert client.put(
        f"/api/nozzles/{nozzle['id']}", json={"totalizer_liters": "99"}
    ).status_code == 400
    assert len(client.get(f"/api/pumps/{data['pump'].id}/nozzles").json()) == 2


def test_topology_create_endpoints_require_admin(topology_api) -> None:
    client, data = topology_api

    def deny_admin() -> None:
        raise HTTPException(status_code=403, detail="Insufficient permissions.")

    app.dependency_overrides[require_admin] = deny_admin
    response = client.post(
        "/api/device-controllers", json=_controller_payload(data["station"].id)
    )
    assert response.status_code == 403
