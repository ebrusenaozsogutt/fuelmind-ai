"""Idempotency tests for the KONYA_TEST simulation demo seed."""

from types import SimpleNamespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.communication_port import CommunicationPort
from app.models.device_controller import DeviceController
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.operations import Attendant, AttendantShiftAssignment, Shift
from app.models.pump import Pump
from app.models.station import Station
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from scripts import seed_demo


class FakeDatabase:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_konya_demo_seed_is_idempotent(monkeypatch) -> None:
    """A repeat seed produces canonical equipment without duplicate records."""

    store = SimpleNamespace(
        station=SimpleNamespace(id=2, code="KONYA_TEST", is_active=True),
        fuels={},
        tanks={},
        pumps={},
        controllers={},
        ports={},
        probes={},
        nozzles={},
    )

    class Stations:
        def __init__(self, _: FakeDatabase) -> None:
            pass

        def get_by_code(self, _: str):
            return store.station

    class Fuels:
        def __init__(self, _: FakeDatabase) -> None:
            pass

        def get_by_code(self, code: str):
            return store.fuels.get(code)

        def create(self, values: dict[str, object]):
            fuel = SimpleNamespace(id=len(store.fuels) + 1, **values)
            store.fuels[fuel.code] = fuel
            return fuel

    class Tanks:
        def __init__(self, _: FakeDatabase) -> None:
            pass

        def get_by_station_and_code(self, _: int, code: str):
            return store.tanks.get(code)

        def create(self, values: dict[str, object]):
            tank = SimpleNamespace(id=len(store.tanks) + 1, **values)
            store.tanks[tank.code] = tank
            return tank

    class Pumps:
        def __init__(self, _: FakeDatabase) -> None:
            pass

        def get_by_station_and_code(self, _: int, code: str):
            return store.pumps.get(code)

        def create(self, values: dict[str, object]):
            pump = SimpleNamespace(
                id=len(store.pumps) + 1,
                communication_port_id=None,
                **values,
            )
            store.pumps[pump.code] = pump
            return pump

    class Controllers:
        def __init__(self, _: FakeDatabase) -> None:
            pass

        def get_by_station_and_code(self, _: int, code: str):
            return store.controllers.get(code)

        def create(self, values: dict[str, object]):
            controller = SimpleNamespace(id=len(store.controllers) + 1, **values)
            store.controllers[controller.code] = controller
            return controller

    class Ports:
        def __init__(self, _: FakeDatabase) -> None:
            pass

        def get_by_controller_and_number(self, controller_id: int, number: int):
            return store.ports.get((controller_id, number))

        def create(self, values: dict[str, object]):
            port = SimpleNamespace(id=len(store.ports) + 1, **values)
            store.ports[(port.controller_id, port.port_number)] = port
            return port

    class Probes:
        def __init__(self, _: FakeDatabase) -> None:
            pass

        def get_active_by_tank(self, tank_id: int):
            return store.probes.get(tank_id)

        def create(self, values: dict[str, object]):
            probe = SimpleNamespace(id=len(store.probes) + 1, **values)
            store.probes[probe.tank_id] = probe
            return probe

    class Nozzles:
        def __init__(self, _: FakeDatabase) -> None:
            pass

        def get_by_pump_and_number(self, pump_id: int, number: int):
            return store.nozzles.get((pump_id, number))

        def create(self, values: dict[str, object]):
            nozzle = SimpleNamespace(id=len(store.nozzles) + 1, **values)
            store.nozzles[(nozzle.pump_id, nozzle.nozzle_number)] = nozzle
            return nozzle

    monkeypatch.setattr(seed_demo, "StationRepository", Stations)
    monkeypatch.setattr(seed_demo, "FuelTypeRepository", Fuels)
    monkeypatch.setattr(seed_demo, "TankRepository", Tanks)
    monkeypatch.setattr(seed_demo, "PumpRepository", Pumps)
    monkeypatch.setattr(seed_demo, "DeviceControllerRepository", Controllers)
    monkeypatch.setattr(seed_demo, "CommunicationPortRepository", Ports)
    monkeypatch.setattr(seed_demo, "TankProbeRepository", Probes)
    monkeypatch.setattr(seed_demo, "NozzleRepository", Nozzles)
    db = FakeDatabase()

    seed_demo.seed_konya_simulation_demo(db)
    seed_demo.seed_konya_simulation_demo(db)

    assert set(store.fuels) == {"DIESEL", "GASOLINE", "LPG"}
    assert len(store.tanks) == 3
    assert len(store.pumps) == 6
    assert {pump.tank_id for pump in store.pumps.values()} == {
        tank.id for tank in store.tanks.values()
    }
    assert len(store.controllers) == 1
    assert {port.port_number for port in store.ports.values()} == {1, 2, 3}
    assert {pump.communication_port_id for pump in store.pumps.values()} == {1, 2}
    assert len(store.probes) == 3
    assert len(store.nozzles) == 6
    assert all(nozzle.totalizer_liters >= 100000 for nozzle in store.nozzles.values())
    assert db.commits == 2


def test_operations_demo_seed_is_idempotent_in_a_real_database(monkeypatch) -> None:
    """The second real database seed keeps the attendant/shift counts unchanged."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        Station.__table__,
        FuelType.__table__,
        Tank.__table__,
        DeviceController.__table__,
        CommunicationPort.__table__,
        Pump.__table__,
        TankProbe.__table__,
        Nozzle.__table__,
        Attendant.__table__,
        Shift.__table__,
        AttendantShiftAssignment.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add(
        Station(
            code="KONYA_TEST",
            name="Konya Test",
            city="Konya",
            district="Selçuklu",
            address="Demo test address",
        )
    )
    session.commit()
    monkeypatch.setattr(seed_demo, "_seed_commercial_demo", lambda *_: None)
    try:
        first = seed_demo.seed_konya_simulation_demo(session)
        first_counts = tuple(
            session.scalar(select(func.count(model.id)))
            for model in (Attendant, Shift, AttendantShiftAssignment)
        )
        second = seed_demo.seed_konya_simulation_demo(session)
        second_counts = tuple(
            session.scalar(select(func.count(model.id)))
            for model in (Attendant, Shift, AttendantShiftAssignment)
        )
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(tables)))
        engine.dispose()

    assert first_counts == second_counts == (6, 3, 6)
    assert first["attendants"] == second["attendants"] == 6
    assert first["shifts"] == second["shifts"] == 3
    assert first["attendant_shift_assignments"] == second["attendant_shift_assignments"] == 6
