"""Acceptance coverage for the additive station live-topology snapshot."""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.communication_port import CommunicationPort
from app.models.device_controller import DeviceController
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.probe_reading import ProbeReading
from app.models.pump import Pump
from app.models.sensor_reading import SensorReading
from app.models.station import Station
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.utils.datetime_utils import utc_now
from app.utils.enums import (
    ControllerStatus,
    NozzleStatus,
    PortStatus,
    PortType,
    ProbeStatus,
    PumpStatus,
    SourceType,
)

_TABLES = [
    Station.__table__,
    FuelType.__table__,
    DeviceController.__table__,
    CommunicationPort.__table__,
    Tank.__table__,
    Pump.__table__,
    TankProbe.__table__,
    Nozzle.__table__,
    SensorReading.__table__,
    ProbeReading.__table__,
]


@pytest.fixture
def topology_live_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    station = Station(code="LIVE-1", name="Live", city="A", district="A", address="A")
    fuel = FuelType(name="Diesel", code="DSL")
    session.add_all([station, fuel])
    session.flush()
    controller = DeviceController(
        station_id=station.id, code="CTRL-1", name="Controller", status=ControllerStatus.ONLINE
    )
    session.add(controller)
    session.flush()
    port = CommunicationPort(
        controller_id=controller.id, port_number=1, name="Field Bus", port_type=PortType.PUMP,
        protocol="RS-485", baud_rate=9600, status=PortStatus.ONLINE,
    )
    session.add(port)
    session.flush()
    tank = Tank(
        station_id=station.id, fuel_type_id=fuel.id, code="T-1", capacity_liters=1000,
        current_level_liters=650, minimum_safe_level=100, critical_level=50,
    )
    session.add(tank)
    session.flush()
    pump = Pump(
        station_id=station.id, tank_id=tank.id, communication_port_id=port.id, code="P-1",
        status=PumpStatus.IDLE, nominal_flow_rate=20, minimum_flow_rate=1,
        maximum_motor_current=10, maximum_pressure=10,
    )
    session.add(pump)
    session.flush()
    probe = TankProbe(
        tank_id=tank.id, communication_port_id=port.id, code="PRB-1", name="Probe",
        status=ProbeStatus.ONLINE,
    )
    nozzle = Nozzle(
        pump_id=pump.id, fuel_type_id=fuel.id, code="NZL-1", nozzle_number=1,
        status=NozzleStatus.AVAILABLE, totalizer_liters=Decimal("125342.9"),
    )
    session.add_all([probe, nozzle])
    session.flush()
    now = utc_now() - timedelta(seconds=1)
    reading = ProbeReading(
        probe_id=probe.id, tank_id=tank.id, reading_timestamp=now,
        fuel_height_mm=1300, fuel_volume_liters=650, water_height_mm=10,
        water_volume_liters=5, temperature_celsius=18.7, data_quality_score=97,
        quality_flags_json=["SENSOR_STUCK"], source_type=SourceType.SIMULATION,
    )
    sensor = SensorReading(
        station_id=station.id, tank_id=tank.id, pump_id=pump.id, reading_timestamp=now,
        flow_rate=0, pressure=0, motor_current=0, pump_temperature=20, error_count=0,
        working_duration=1, data_quality_score=100, source_type=SourceType.SIMULATION,
    )
    session.add_all([reading, sensor])
    session.commit()
    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    try:
        with TestClient(app) as client:
            yield client, station, controller, port, probe, nozzle, pump
    finally:
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()


def test_live_status_returns_current_flat_topology_and_probe_measurement(topology_live_api) -> None:
    client, station, controller, port, probe, nozzle, pump = topology_live_api

    response = client.get(f"/api/stations/{station.id}/live-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["controllers"][0]["id"] == controller.id
    assert payload["ports"][0]["controller_id"] == controller.id
    assert payload["probes"][0]["communication_port_id"] == port.id
    assert payload["probes"][0]["fuel_volume_liters"] == 650
    assert payload["probes"][0]["quality_flags"] == ["SENSOR_STUCK"]
    assert payload["nozzles"][0]["pump_id"] == pump.id
    assert payload["nozzles"][0]["totalizer_liters"] == 125342.9
    assert payload["pumps"][0]["communication_port_id"] == port.id


def test_live_status_openapi_exposes_additive_topology_models(topology_live_api) -> None:
    client, *_ = topology_live_api

    document = client.get("/openapi.json").json()
    schema = document["components"]["schemas"]["LiveStatusRead"]

    assert {"controllers", "ports", "probes", "nozzles"} <= set(
        schema["properties"]
    )
    for name in ("ControllerLive", "CommunicationPortLive", "ProbeLive", "NozzleLive"):
        assert name in document["components"]["schemas"]
