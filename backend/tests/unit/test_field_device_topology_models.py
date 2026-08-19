"""Model-level coverage for Stage 9 field-device topology."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.communication_port import CommunicationPort
from app.models.device_controller import DeviceController
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.probe_reading import ProbeReading
from app.models.pump import Pump
from app.models.station import Station
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.utils.datetime_utils import utc_now
from app.utils.enums import (
    ControllerStatus,
    ControllerType,
    NozzleStatus,
    PortStatus,
    PortType,
    ProbeStatus,
    PumpStatus,
    SourceType,
)


_TOPOLOGY_TABLES = [
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
def topology_session() -> Session:
    """Provide isolated SQLite storage for database constraint checks."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TOPOLOGY_TABLES)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(_TOPOLOGY_TABLES)))
        engine.dispose()


def _equipment(session: Session) -> tuple[Station, FuelType, Tank, Pump]:
    station = Station(
        code="S-1", name="Station", city="Istanbul", district="Kadikoy", address="A"
    )
    fuel_type = FuelType(name="Diesel", code="DSL")
    session.add_all([station, fuel_type])
    session.flush()
    tank = Tank(
        station_id=station.id,
        fuel_type_id=fuel_type.id,
        code="T-1",
        capacity_liters=Decimal("1000"),
        current_level_liters=Decimal("500"),
        minimum_safe_level=Decimal("100"),
        critical_level=Decimal("50"),
    )
    session.add(tank)
    session.flush()
    pump = Pump(
        station_id=station.id,
        tank_id=tank.id,
        code="P-1",
        status=PumpStatus.IDLE,
        nominal_flow_rate=Decimal("10"),
        minimum_flow_rate=Decimal("1"),
        maximum_motor_current=Decimal("10"),
        maximum_pressure=Decimal("10"),
    )
    session.add(pump)
    session.flush()
    return station, fuel_type, tank, pump


def _controller_and_port(
    session: Session, station: Station, *, port_number: int = 1
) -> tuple[DeviceController, CommunicationPort]:
    controller = DeviceController(
        station_id=station.id,
        code="CTRL-1",
        name="Forecourt Controller",
        controller_type=ControllerType.GENERIC,
        status=ControllerStatus.ONLINE,
    )
    session.add(controller)
    session.flush()
    port = CommunicationPort(
        controller_id=controller.id,
        port_number=port_number,
        name=f"Port {port_number}",
        port_type=PortType.PUMP,
        status=PortStatus.ONLINE,
    )
    session.add(port)
    session.flush()
    return controller, port


def test_station_can_own_controller_and_controller_can_own_ports(
    topology_session: Session,
) -> None:
    station, _, _, _ = _equipment(topology_session)
    controller, first_port = _controller_and_port(topology_session, station)
    second_port = CommunicationPort(
        controller_id=controller.id,
        port_number=2,
        name="Probe Port",
        port_type=PortType.PROBE,
        status=PortStatus.OFFLINE,
    )
    topology_session.add(second_port)
    topology_session.commit()

    assert station.device_controllers == [controller]
    assert controller.communication_ports == [first_port, second_port]


def test_duplicate_port_number_is_rejected_per_controller(
    topology_session: Session,
) -> None:
    station, _, _, _ = _equipment(topology_session)
    controller, _ = _controller_and_port(topology_session, station)
    topology_session.add(
        CommunicationPort(
            controller_id=controller.id,
            port_number=1,
            name="Duplicate Port",
            port_type=PortType.PUMP,
            status=PortStatus.ONLINE,
        )
    )

    with pytest.raises(IntegrityError):
        topology_session.commit()


def test_pump_can_optionally_reference_communication_port(
    topology_session: Session,
) -> None:
    station, _, _, pump = _equipment(topology_session)
    _, port = _controller_and_port(topology_session, station)
    pump.communication_port_id = port.id
    pump.device_address = "PUMP-01"
    topology_session.commit()

    assert pump.communication_port is port
    assert port.pumps == [pump]


def test_tank_probe_and_reading_can_be_created(topology_session: Session) -> None:
    station, _, tank, _ = _equipment(topology_session)
    _, port = _controller_and_port(topology_session, station)
    probe = TankProbe(
        tank_id=tank.id,
        communication_port_id=port.id,
        code="PRB-1",
        name="Tank Probe",
        status=ProbeStatus.ONLINE,
    )
    topology_session.add(probe)
    topology_session.flush()
    reading = ProbeReading(
        probe_id=probe.id,
        tank_id=tank.id,
        sequence_number=1,
        reading_timestamp=utc_now(),
        fuel_height_mm=Decimal("850"),
        fuel_volume_liters=Decimal("500"),
        water_height_mm=Decimal("1"),
        data_quality_score=Decimal("99"),
        source_type=SourceType.SIMULATION,
    )
    topology_session.add(reading)
    topology_session.commit()

    assert tank.tank_probes == [probe]
    assert probe.readings == [reading]


def test_pump_can_own_multiple_nozzles(topology_session: Session) -> None:
    _, fuel_type, _, pump = _equipment(topology_session)
    first = Nozzle(
        pump_id=pump.id,
        fuel_type_id=fuel_type.id,
        code="N-1",
        nozzle_number=1,
        status=NozzleStatus.AVAILABLE,
        totalizer_liters=Decimal("0"),
    )
    second = Nozzle(
        pump_id=pump.id,
        fuel_type_id=fuel_type.id,
        code="N-2",
        nozzle_number=2,
        status=NozzleStatus.AVAILABLE,
        totalizer_liters=Decimal("10"),
    )
    topology_session.add_all([first, second])
    topology_session.commit()

    assert pump.nozzles == [first, second]
    assert fuel_type.nozzles == [first, second]


def test_duplicate_nozzle_number_is_rejected_per_pump(
    topology_session: Session,
) -> None:
    _, fuel_type, _, pump = _equipment(topology_session)
    topology_session.add_all(
        [
            Nozzle(
                pump_id=pump.id,
                fuel_type_id=fuel_type.id,
                code="N-1",
                nozzle_number=1,
                status=NozzleStatus.AVAILABLE,
                totalizer_liters=Decimal("0"),
            ),
            Nozzle(
                pump_id=pump.id,
                fuel_type_id=fuel_type.id,
                code="N-2",
                nozzle_number=1,
                status=NozzleStatus.AVAILABLE,
                totalizer_liters=Decimal("0"),
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        topology_session.commit()


def test_negative_nozzle_totalizer_is_rejected(topology_session: Session) -> None:
    _, fuel_type, _, pump = _equipment(topology_session)
    topology_session.add(
        Nozzle(
            pump_id=pump.id,
            fuel_type_id=fuel_type.id,
            code="N-1",
            nozzle_number=1,
            status=NozzleStatus.AVAILABLE,
            totalizer_liters=Decimal("-1"),
        )
    )

    with pytest.raises(IntegrityError):
        topology_session.commit()
