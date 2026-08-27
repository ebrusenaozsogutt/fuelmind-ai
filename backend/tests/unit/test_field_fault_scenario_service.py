"""Field communication scenarios reuse topology state and alarm deduplication."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.alarm import Alarm
from app.models.communication_port import CommunicationPort
from app.models.device_controller import DeviceController
from app.models.fuel_type import FuelType
from app.models.pump import Pump
from app.models.station import Station
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.models.user import User
from app.services.field_fault_scenario_service import FieldFaultScenarioService
from app.utils.enums import (
    ControllerStatus,
    ControllerType,
    PortStatus,
    PortType,
    ProbeStatus,
    PumpStatus,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_: JSONB, __, **___) -> str:
    return "JSON"


def test_field_scenarios_update_device_state_and_deduplicate_alarm() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    tables = [User.__table__, Station.__table__, FuelType.__table__, Tank.__table__, DeviceController.__table__, CommunicationPort.__table__, Pump.__table__, TankProbe.__table__, Alarm.__table__]
    Base.metadata.create_all(engine, tables=tables)
    session = sessionmaker(bind=engine)()
    station = Station(code="S", name="Station", city="A", district="A", address="A")
    fuel = FuelType(code="DSL", name="Diesel")
    session.add_all([station, fuel])
    session.flush()
    tank = Tank(station_id=station.id, fuel_type_id=fuel.id, code="T", capacity_liters=Decimal("1000"), current_level_liters=Decimal("500"), minimum_safe_level=Decimal("100"), critical_level=Decimal("50"), water_level=Decimal("0"))
    controller = DeviceController(station_id=station.id, code="USC", name="USC", controller_type=ControllerType.USC, status=ControllerStatus.ONLINE)
    session.add_all([tank, controller])
    session.flush()
    port = CommunicationPort(controller_id=controller.id, port_number=1, name="Bus", port_type=PortType.PUMP, status=PortStatus.ONLINE)
    session.add(port)
    session.flush()
    pump = Pump(station_id=station.id, tank_id=tank.id, communication_port_id=port.id, code="P", status=PumpStatus.IDLE, nominal_flow_rate=Decimal("30"), minimum_flow_rate=Decimal("5"), maximum_motor_current=Decimal("10"), maximum_pressure=Decimal("5"))
    probe = TankProbe(tank_id=tank.id, communication_port_id=port.id, code="PRB", name="Probe", status=ProbeStatus.ONLINE)
    session.add_all([pump, probe])
    session.commit()

    service = FieldFaultScenarioService(session)
    moment = datetime(2026, 8, 26, tzinfo=timezone.utc)
    port_scenario = [{"scenario_type": "PORT_COMMUNICATION_ERROR", "target_id": port.id}]
    assert len(service.apply(port_scenario, moment)) == 1
    assert service.apply(port_scenario, moment) == []
    assert session.get(CommunicationPort, port.id).status is PortStatus.OFFLINE
    alarm = session.scalar(select(Alarm).where(Alarm.alarm_type == "PORT_COMMUNICATION_ERROR"))
    assert alarm is not None and alarm.target_type == "PORT" and alarm.target_id == port.id

    service.apply([], moment)
    assert session.get(CommunicationPort, port.id).status is PortStatus.ONLINE

    active_faults = [
        {"scenario_type": "USC_INITIALIZATION_ERROR", "target_id": controller.id},
        {"scenario_type": "PROBE_COMMUNICATION_ERROR", "target_id": probe.id},
        {"scenario_type": "PUMP_NOT_CONNECTED", "target_id": pump.id},
    ]
    service.apply(active_faults, moment)
    assert session.get(DeviceController, controller.id).status is ControllerStatus.ERROR
    assert session.get(TankProbe, probe.id).status is ProbeStatus.OFFLINE
    assert session.get(Pump, pump.id).status is PumpStatus.OFFLINE
    service.apply([], moment)
    assert session.get(DeviceController, controller.id).status is ControllerStatus.ONLINE
    assert session.get(CommunicationPort, port.id).status is PortStatus.ONLINE
    assert session.get(TankProbe, probe.id).status is ProbeStatus.ONLINE
    assert session.get(Pump, pump.id).status is PumpStatus.IDLE

    port.status = PortStatus.OFFLINE
    pump.status = PumpStatus.MAINTENANCE
    session.flush()
    service.apply(port_scenario, moment)
    service.apply([], moment)
    assert port.status is PortStatus.OFFLINE
    service.apply([{"scenario_type": "PUMP_NOT_CONNECTED", "target_id": pump.id}], moment)
    service.apply([], moment)
    assert pump.status is PumpStatus.MAINTENANCE
    service.apply([{"scenario_type": "USC_INITIALIZATION_ERROR", "target_id": controller.id}], moment)
    service.apply([], moment)
    assert port.status is PortStatus.OFFLINE
    session.close()
    Base.metadata.drop_all(engine, tables=list(reversed(tables)))
    engine.dispose()
