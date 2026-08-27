"""Stage 12.1 acceptance coverage for rich, historical dataset generation."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.ml.forecast_dataset_loader import ForecastRawDatasetLoader
from app.ml.demand_preprocessing import DemandForecastDatasetBuilder
from app.ml.demand_model import SevenDayMovingAverageBaseline
from app.services.demand_training_service import DemandTrainingService
from app.models.commercial import (
    Customer,
    Fleet,
    FleetGroup,
    FuelCard,
    FuelCardAllowedFuelType,
    FuelCardAllowedStation,
    FuelCardLimit,
    FuelPrice,
    FuelCardUsageWindow,
    Vehicle,
    Driver,
    DriverVehicleAssignment,
)
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.operations import Attendant, AttendantShiftAssignment, Shift
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.model_version import ModelVersion
from app.models.sensor_reading import SensorReading
from app.models.simulation_run import SimulationRun
from app.models.station import Station
from app.models.tank import Tank
from app.models.user import User
from app.simulation.dataset_generator import DatasetGenerator
from app.simulation.dependencies import build_simulation_runner
from app.utils.enums import (
    CardStatus,
    CustomerType,
    NozzleStatus,
    PaymentType,
    PumpStatus,
    SimulationMode,
    SimulationStatus,
    SaleStatus,
)


_TABLES = [
    User.__table__,
    Station.__table__,
    FuelType.__table__,
    Customer.__table__,
    Fleet.__table__,
    FleetGroup.__table__,
    Vehicle.__table__,
    Driver.__table__,
    DriverVehicleAssignment.__table__,
    FuelCard.__table__,
    FuelCardAllowedStation.__table__,
    FuelCardAllowedFuelType.__table__,
    FuelCardLimit.__table__,
    FuelCardUsageWindow.__table__,
    FuelPrice.__table__,
    Tank.__table__,
    Pump.__table__,
    Nozzle.__table__,
    Attendant.__table__,
    Shift.__table__,
    AttendantShiftAssignment.__table__,
    SimulationRun.__table__,
    SensorReading.__table__,
    Sale.__table__,
    ModelVersion.__table__,
]


@pytest.fixture
def forecast_dataset_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    start = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
    station = Station(code="FC-1", name="Forecast", city="Konya", district="Selcuklu", address="A")
    fuel = FuelType(code="DIESEL", name="Diesel")
    session.add_all([station, fuel])
    session.flush()
    tank = Tank(
        station_id=station.id,
        fuel_type_id=fuel.id,
        code="T-1",
        capacity_liters=Decimal("100000"),
        current_level_liters=Decimal("90000"),
        minimum_safe_level=Decimal("1000"),
        critical_level=Decimal("500"),
        water_level=Decimal("0"),
    )
    session.add(tank)
    session.flush()
    pump = Pump(
        station_id=station.id,
        tank_id=tank.id,
        code="P-1",
        status=PumpStatus.IDLE,
        nominal_flow_rate=Decimal("42"),
        minimum_flow_rate=Decimal("10"),
        maximum_motor_current=Decimal("20"),
        maximum_pressure=Decimal("8"),
    )
    session.add(pump)
    session.flush()
    nozzle = Nozzle(
        pump_id=pump.id,
        fuel_type_id=fuel.id,
        code="N-1",
        nozzle_number=1,
        status=NozzleStatus.AVAILABLE,
        totalizer_liters=Decimal("1000"),
    )
    customer = Customer(
        code="FORECAST-CUSTOMER",
        name="Forecast Customer",
        customer_type=CustomerType.COMPANY,
        discount_rate=Decimal("3"),
    )
    session.add_all([nozzle, customer])
    session.flush()
    fleet = Fleet(customer_id=customer.id, code="F-1", name="Fleet")
    session.add(fleet)
    session.flush()
    group = FleetGroup(fleet_id=fleet.id, code="G-1", name="Group")
    session.add(group)
    session.flush()
    vehicle = Vehicle(fleet_group_id=group.id, plate="42 FC 001")
    session.add(vehicle)
    session.flush()
    card = FuelCard(
        vehicle_id=vehicle.id,
        card_code="FC-CARD",
        display_name="Forecast Card",
        unit_id="FC-UNIT",
        status=CardStatus.ACTIVE,
        valid_from=date(2020, 1, 1),
        payment_type=PaymentType.CREDIT,
        credit_limit=Decimal("1000000"),
    )
    attendant = Attendant(
        station_id=station.id,
        code="ATT-1",
        full_name="Forecast Attendant",
        employee_number="FC-ATT-1",
    )
    shift = Shift(
        station_id=station.id,
        code="DAY",
        name="Day",
        start_time=time(8),
        end_time=time(16),
    )
    session.add_all([card, attendant, shift])
    session.flush()
    session.add_all(
        [
            FuelCardAllowedStation(fuel_card_id=card.id, station_id=station.id),
            FuelCardAllowedFuelType(fuel_card_id=card.id, fuel_type_id=fuel.id),
            AttendantShiftAssignment(
                station_id=station.id,
                attendant_id=attendant.id,
                shift_id=shift.id,
            ),
            FuelPrice(
                station_id=station.id,
                fuel_type_id=fuel.id,
                unit_price=Decimal("55.0000"),
                effective_from=start - timedelta(days=1),
            ),
            SimulationRun(
                station_id=station.id,
                mode=SimulationMode.DATASET,
                status=SimulationStatus.CREATED,
                simulation_start_time=start,
                current_simulation_time=start,
                target_simulation_time=start + timedelta(days=90),
                simulation_step_seconds=86_400,
                random_seed=42,
            ),
        ]
    )
    session.commit()
    run = session.scalar(select(SimulationRun))
    assert run is not None
    try:
        yield factory, session, {
            "run": run,
            "station": station,
            "tank": tank,
            "pump": pump,
            "nozzle": nozzle,
            "customer": customer,
            "vehicle": vehicle,
            "card": card,
            "attendant": attendant,
            "shift": shift,
            "start": start,
        }
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()


@pytest.mark.asyncio
async def test_ninety_day_dataset_uses_price_and_domain_relationship_snapshots(
    forecast_dataset_db, tmp_path,
) -> None:
    factory, session, data = forecast_dataset_db
    runner = build_simulation_runner(data["run"].id, session_factory=factory)
    original_run_tick = runner.tick_engine.run_tick

    def run_tick_without_events(state):
        result = original_run_tick(state)
        result.events = []
        return result

    runner.tick_engine.run_tick = run_tick_without_events

    await DatasetGenerator(runner=runner, days=90, session_factory=factory).generate()

    session.expire_all()
    run = session.get(SimulationRun, data["run"].id)
    sales = list(session.scalars(select(Sale).order_by(Sale.sale_timestamp, Sale.id)))
    assert run is not None
    assert run.status == SimulationStatus.COMPLETED
    assert run.current_simulation_time.replace(tzinfo=timezone.utc) == data["start"] + timedelta(days=90)
    assert run.sequence_number == 90
    assert sales
    assert all(sale.sale_status == SaleStatus.COMPLETED for sale in sales)
    assert all(sale.station_id == data["station"].id for sale in sales)
    assert all(sale.tank_id == data["tank"].id for sale in sales)
    assert all(sale.pump_id == data["pump"].id for sale in sales)
    assert all(sale.nozzle_id == data["nozzle"].id for sale in sales)
    assert all(sale.fuel_type_id == data["tank"].fuel_type_id for sale in sales)
    assert all(sale.customer_id == data["customer"].id for sale in sales)
    assert all(sale.vehicle_id == data["vehicle"].id for sale in sales)
    assert all(sale.fuel_card_id == data["card"].id for sale in sales)
    assert all(sale.attendant_id == data["attendant"].id for sale in sales)
    assert all(sale.shift_id == data["shift"].id for sale in sales)
    assert all(sale.unit_price == Decimal("53.3500") for sale in sales)
    assert all(
        sale.total_amount
        == (sale.quantity_liters * sale.unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        for sale in sales
    )
    assert all(
        sale.end_totalizer_liters - sale.start_totalizer_liters == sale.quantity_liters
        for sale in sales
    )
    assert all(
        earlier.end_totalizer_liters == later.start_totalizer_liters
        for earlier, later in zip(sales, sales[1:])
    )

    loaded = ForecastRawDatasetLoader(session).load(
        station_id=data["station"].id,
        start_at=data["start"],
        end_at=data["start"] + timedelta(days=90, seconds=1),
    )
    assert [row.sale_id for row in loaded] == [sale.id for sale in sales]
    demand_dataset = DemandForecastDatasetBuilder(session).build(
        station_id=data["station"].id,
        start_at=data["start"],
        end_at=data["start"] + timedelta(days=90, seconds=1),
    )
    assert demand_dataset.summary.raw_sales > 0
    assert demand_dataset.summary.daily_rows > 0
    assert demand_dataset.summary.model_ready_rows > 0
    assert demand_dataset.daily_dataframe.date.is_monotonic_increasing
    assert all(count >= 15 for count in demand_dataset.summary.series_row_counts.values())
    evaluation = SevenDayMovingAverageBaseline().evaluate(demand_dataset.feature_dataframe)
    assert evaluation.train_row_count > 0
    assert evaluation.test_row_count > 0
    assert len(evaluation.predictions) > 0
    assert evaluation.mae >= 0
    assert evaluation.rmse >= 0
    assert evaluation.mape is None or evaluation.mape >= 0
    assert (evaluation.predictions.predicted_demand >= 0).all()
    anomaly_record = ModelVersion(
        model_type="isolation_forest", model_family="pump", version="v0001",
        file_path="trained_models/anomaly/existing.joblib", artifact_sha256="0" * 64,
        artifact_size_bytes=1, metadata_json={}, training_start_date=data["start"].date(),
        training_end_date=data["start"].date(), training_row_count=1, is_active=True,
    )
    session.add(anomaly_record)
    session.commit()
    training = DemandTrainingService(
        session, registry_root=tmp_path / "trained_models"
    ).train(station_id=data["station"].id, start_at=data["start"].date())
    record = training.registry_record
    artifact_path = tmp_path / record.file_path
    loaded_artifact = DemandTrainingService.load_artifact(artifact_path)
    assert artifact_path.is_file()
    assert loaded_artifact.models
    assert record.model_type == "demand_xgboost"
    assert record.training_row_count == training.xgboost.train_row_count
    assert record.is_active is (training.winner == "xgboost")
    assert session.get(ModelVersion, anomaly_record.id).is_active is True

    original_price = session.scalar(select(FuelPrice))
    assert original_price is not None
    original_price.effective_until = data["start"] + timedelta(days=91)
    session.add(
        FuelPrice(
            station_id=data["station"].id,
            fuel_type_id=data["tank"].fuel_type_id,
            unit_price=Decimal("60.0000"),
            effective_from=data["start"] + timedelta(days=91),
        )
    )
    session.commit()
    session.expire_all()
    assert all(
        sale.unit_price == Decimal("53.3500")
        for sale in session.scalars(select(Sale).where(Sale.simulation_run_id == run.id))
    )


@pytest.mark.asyncio
async def test_dataset_sales_are_deterministic_for_the_same_seed_and_start(
    forecast_dataset_db,
) -> None:
    factory, session, data = forecast_dataset_db

    async def generate(run_id: int) -> list[Sale]:
        runner = build_simulation_runner(run_id, session_factory=factory)
        original_run_tick = runner.tick_engine.run_tick

        def run_tick_without_events(state):
            result = original_run_tick(state)
            result.events = []
            return result

        runner.tick_engine.run_tick = run_tick_without_events
        await DatasetGenerator(runner=runner, days=90, session_factory=factory).generate()
        session.expire_all()
        return list(
            session.scalars(
                select(Sale)
                .where(Sale.simulation_run_id == run_id)
                .order_by(Sale.sale_timestamp, Sale.id)
            )
        )

    first = await generate(data["run"].id)
    second_run = SimulationRun(
        station_id=data["station"].id,
        mode=SimulationMode.DATASET,
        status=SimulationStatus.CREATED,
        simulation_start_time=data["start"],
        current_simulation_time=data["start"],
        target_simulation_time=data["start"] + timedelta(days=90),
        simulation_step_seconds=86_400,
        random_seed=42,
    )
    session.add(second_run)
    session.commit()
    second = await generate(second_run.id)

    assert [
        (
            sale.sale_timestamp.replace(tzinfo=timezone.utc),
            sale.station_id,
            sale.pump_id,
            sale.nozzle_id,
            sale.fuel_type_id,
            sale.customer_id,
            sale.vehicle_id,
            sale.fuel_card_id,
            sale.attendant_id,
            sale.shift_id,
            sale.quantity_liters,
            sale.unit_price,
        )
        for sale in first
    ] == [
        (
            sale.sale_timestamp.replace(tzinfo=timezone.utc),
            sale.station_id,
            sale.pump_id,
            sale.nozzle_id,
            sale.fuel_type_id,
            sale.customer_id,
            sale.vehicle_id,
            sale.fuel_card_id,
            sale.attendant_id,
            sale.shift_id,
            sale.quantity_liters,
            sale.unit_price,
        )
        for sale in second
    ]
