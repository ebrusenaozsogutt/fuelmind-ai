"""Idempotency tests for the KONYA_TEST simulation demo seed."""

from types import SimpleNamespace

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
    )

    class Stations:
        def __init__(self, _: FakeDatabase) -> None:
            pass

        def get(self, _: int):
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
            pump = SimpleNamespace(id=len(store.pumps) + 1, **values)
            store.pumps[pump.code] = pump
            return pump

    monkeypatch.setattr(seed_demo, "StationRepository", Stations)
    monkeypatch.setattr(seed_demo, "FuelTypeRepository", Fuels)
    monkeypatch.setattr(seed_demo, "TankRepository", Tanks)
    monkeypatch.setattr(seed_demo, "PumpRepository", Pumps)
    db = FakeDatabase()

    seed_demo.seed_konya_simulation_demo(db)
    seed_demo.seed_konya_simulation_demo(db)

    assert set(store.fuels) == {"DIESEL", "GASOLINE", "LPG"}
    assert len(store.tanks) == 3
    assert len(store.pumps) == 6
    assert {pump.tank_id for pump in store.pumps.values()} == {
        tank.id for tank in store.tanks.values()
    }
    assert db.commits == 2
