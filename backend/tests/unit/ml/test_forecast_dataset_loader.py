"""Raw-sale boundary tests for the Stage 12 forecasting dataset."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.ml.forecast_dataset_loader import ForecastRawDatasetLoader
from app.models.communication_port import CommunicationPort
from app.models.commercial import Customer, Driver, Fleet, FleetGroup, FuelCard, Vehicle
from app.models.device_controller import DeviceController
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.operations import Attendant, Shift
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.simulation_run import SimulationRun
from app.models.station import Station
from app.models.tank import Tank
from app.models.user import User
from app.utils.enums import PumpStatus, SaleStatus


_TABLES = [
    User.__table__,
    Station.__table__,
    FuelType.__table__,
    Customer.__table__,
    Fleet.__table__,
    FleetGroup.__table__,
    Vehicle.__table__,
    Driver.__table__,
    FuelCard.__table__,
    DeviceController.__table__,
    CommunicationPort.__table__,
    Tank.__table__,
    Pump.__table__,
    Nozzle.__table__,
    Attendant.__table__,
    Shift.__table__,
    SimulationRun.__table__,
    Sale.__table__,
]


@pytest.fixture
def sales_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=_TABLES)
    factory = sessionmaker(bind=engine)
    session = factory()
    station = Station(code="ML-1", name="ML", city="Konya", district="Selcuklu", address="A")
    fuel = FuelType(code="DIESEL", name="Diesel")
    session.add_all([station, fuel])
    session.flush()
    tank = Tank(
        station_id=station.id,
        fuel_type_id=fuel.id,
        code="T-1",
        capacity_liters=Decimal("1000"),
        current_level_liters=Decimal("800"),
        minimum_safe_level=Decimal("100"),
        critical_level=Decimal("50"),
        water_level=Decimal("0"),
    )
    session.add(tank)
    session.flush()
    pump = Pump(
        station_id=station.id,
        tank_id=tank.id,
        code="P-1",
        status=PumpStatus.IDLE,
        nominal_flow_rate=Decimal("40"),
        minimum_flow_rate=Decimal("10"),
        maximum_motor_current=Decimal("20"),
        maximum_pressure=Decimal("8"),
    )
    session.add(pump)
    session.flush()

    def sale(at: datetime, status: SaleStatus, amount: str) -> Sale:
        return Sale(
            station_id=station.id,
            tank_id=tank.id,
            pump_id=pump.id,
            fuel_type_id=fuel.id,
            sale_timestamp=at,
            quantity_liters=Decimal("10"),
            unit_price=Decimal("55"),
            total_amount=Decimal(amount),
            sale_status=status,
            duration_seconds=1,
            level_before=Decimal("800"),
            level_after=Decimal("790"),
            is_anomaly=False,
        )

    session.add_all(
        [
            sale(datetime(2026, 1, 1, 10, tzinfo=timezone.utc), SaleStatus.COMPLETED, "550"),
            sale(datetime(2026, 1, 2, 10, tzinfo=timezone.utc), SaleStatus.CANCELLED, "550"),
            sale(datetime(2026, 1, 3, 10, tzinfo=timezone.utc), SaleStatus.COMPLETED, "550"),
        ]
    )
    session.commit()
    try:
        yield session, station
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()


def test_loader_returns_only_completed_rows_in_chronological_half_open_range(sales_session) -> None:
    session, station = sales_session

    rows = ForecastRawDatasetLoader(session).load(
        station_id=station.id,
        start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    assert len(rows) == 1
    assert rows[0].sale_status == SaleStatus.COMPLETED
    assert rows[0].station_id == station.id
    assert rows[0].quantity_liters == Decimal("10.000")
    assert rows[0].total_amount == Decimal("550.00")


def test_loader_requires_aware_datetime_boundaries(sales_session) -> None:
    session, _ = sales_session

    with pytest.raises(ValueError, match="timezone"):
        ForecastRawDatasetLoader(session).load(start_at=datetime(2026, 1, 1))
