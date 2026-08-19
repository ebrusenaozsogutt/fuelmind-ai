"""Unit coverage for read-only anomaly-training dataset selection."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ml.preprocessing import AnomalyTrainingDatasetBuilder, RAW_TRAINING_COLUMNS
from app.database import Base
from app.models.fuel_type import FuelType
from app.models.pump import Pump
from app.models.sensor_reading import SensorReading
from app.models.simulation_run import SimulationRun
from app.models.simulation_scenario import SimulationScenario
from app.models.station import Station
from app.models.tank import Tank
from app.utils.datetime_utils import utc_now
from app.utils.enums import PumpStatus, SimulationMode, SimulationStatus, SimulationTargetType, SourceType


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_: JSONB, __, **___) -> str:
    return "JSON"


_TABLES = [
    Station.__table__, FuelType.__table__, Tank.__table__, Pump.__table__,
    SimulationRun.__table__, SimulationScenario.__table__, SensorReading.__table__,
]


@pytest.fixture
def dataset_db() -> tuple[Session, dict[str, object]]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=_TABLES)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    now = utc_now().replace(microsecond=0)
    fuel = FuelType(name="Diesel", code="DSL")
    station = Station(code="ML-1", name="ML station", city="A", district="A", address="A")
    other_station = Station(code="ML-2", name="Other station", city="B", district="B", address="B")
    session.add_all([fuel, station, other_station])
    session.flush()
    tank = Tank(station_id=station.id, fuel_type_id=fuel.id, code="T-1", capacity_liters=1000, current_level_liters=500, minimum_safe_level=100, critical_level=50)
    other_tank = Tank(station_id=other_station.id, fuel_type_id=fuel.id, code="T-2", capacity_liters=1000, current_level_liters=500, minimum_safe_level=100, critical_level=50)
    session.add_all([tank, other_tank])
    session.flush()
    pump = Pump(station_id=station.id, tank_id=tank.id, code="P-1", status=PumpStatus.ACTIVE, nominal_flow_rate=10, minimum_flow_rate=1, maximum_motor_current=15, maximum_pressure=10)
    session.add(pump)
    session.flush()
    run = SimulationRun(station_id=station.id, mode=SimulationMode.DATASET, status=SimulationStatus.COMPLETED, simulation_start_time=now - timedelta(hours=1))
    session.add(run)
    session.commit()
    try:
        yield session, {"station": station, "other_station": other_station, "tank": tank, "other_tank": other_tank, "pump": pump, "run": run, "now": now}
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()


def _reading(data: dict[str, object], *, timestamp, sequence: int, **overrides: object) -> SensorReading:
    station = data["station"]
    tank = data["tank"]
    pump = data["pump"]
    run = data["run"]
    values: dict[str, object] = {
        "station_id": station.id, "tank_id": tank.id, "pump_id": pump.id,
        "simulation_run_id": run.id, "sequence_number": sequence, "reading_timestamp": timestamp,
        "tank_level": Decimal("500"), "true_tank_level": Decimal("501"), "temperature": Decimal("20"),
        "water_level": Decimal("1"), "flow_rate": Decimal("5"), "pressure": Decimal("3"),
        "motor_current": Decimal("9"), "pump_temperature": Decimal("27"), "error_count": 0,
        "working_duration": Decimal("3"), "data_quality_score": Decimal("95"), "quality_flags_json": [],
        "is_anomaly": False, "source_type": SourceType.SIMULATION,
    }
    values.update(overrides)
    return SensorReading(**values)


def _build(session: Session, data: dict[str, object], **kwargs: object):
    return AnomalyTrainingDatasetBuilder(session).build(station_id=data["station"].id, **kwargs)


def test_normal_quality_reading_is_selected_with_raw_columns(dataset_db) -> None:
    session, data = dataset_db
    session.add(_reading(data, timestamp=data["now"], sequence=1))
    session.commit()

    result = _build(session, data)

    assert result.summary.included == 1
    assert tuple(result.dataframe.columns) == RAW_TRAINING_COLUMNS
    assert result.dataframe.iloc[0]["source_type"] == SourceType.SIMULATION.value


def test_quality_threshold_and_critical_quality_flag_exclude_readings(dataset_db) -> None:
    session, data = dataset_db
    session.add_all([
        _reading(data, timestamp=data["now"], sequence=1, data_quality_score=Decimal("69")),
        _reading(data, timestamp=data["now"] + timedelta(minutes=1), sequence=2, quality_flags_json=["SENSOR_STUCK"]),
    ])
    session.commit()

    result = _build(session, data)

    assert result.summary.total_examined == 2
    assert result.summary.excluded_quality == 2
    assert result.summary.included == 0


def test_known_anomaly_filter_can_be_disabled(dataset_db) -> None:
    session, data = dataset_db
    session.add(_reading(data, timestamp=data["now"], sequence=1, is_anomaly=True))
    session.commit()

    excluded = _build(session, data)
    included = _build(session, data, exclude_known_anomalies=False)

    assert excluded.summary.excluded_anomaly == 1 and excluded.dataframe.empty
    assert included.summary.included == 1


def test_active_targeted_scenario_is_excluded_by_default(dataset_db) -> None:
    session, data = dataset_db
    now = data["now"]
    session.add(SimulationScenario(
        simulation_run_id=data["run"].id, name="Flow drop", scenario_type="FLOW_DROP",
        target_type=SimulationTargetType.PUMP, target_id=data["pump"].id,
        start_time=now, duration_minutes=10, parameters_json={}, status=SimulationStatus.CREATED,
    ))
    session.add_all([
        _reading(data, timestamp=now + timedelta(minutes=1), sequence=1),
        _reading(data, timestamp=now + timedelta(minutes=11), sequence=2),
    ])
    session.commit()

    excluded = _build(session, data)
    included = _build(session, data, exclude_active_scenarios=False)

    assert excluded.summary.excluded_scenario == 1
    assert excluded.dataframe["sequence_number"].tolist() == [2]
    assert included.dataframe["sequence_number"].tolist() == [1, 2]


def test_time_station_and_source_filters_are_applied_in_database(dataset_db) -> None:
    session, data = dataset_db
    now = data["now"]
    session.add_all([
        _reading(data, timestamp=now - timedelta(hours=1), sequence=1),
        _reading(data, timestamp=now, sequence=2, source_type=SourceType.MANUAL),
        _reading(data, timestamp=now + timedelta(hours=1), sequence=3),
        _reading(data, timestamp=now, sequence=4, station_id=data["other_station"].id, tank_id=data["other_tank"].id),
    ])
    session.commit()

    result = _build(session, data, start_time=now - timedelta(minutes=1), end_time=now + timedelta(minutes=1), source_types=[SourceType.MANUAL])

    assert result.dataframe["sequence_number"].tolist() == [2]
    assert result.summary.source_type_distribution == {"MANUAL": 1}
    assert result.summary.raw_station_rows == 3
    assert result.summary.rows_after_date_filter == 1
    assert result.summary.rows_after_source_filter == 1
    assert result.summary.excluded_date == 2
    assert result.summary.excluded_source == 0


def test_results_are_chronological_and_non_finite_values_are_excluded(dataset_db) -> None:
    session, data = dataset_db
    now = data["now"]
    session.add_all([
        _reading(data, timestamp=now + timedelta(minutes=2), sequence=3),
        _reading(data, timestamp=now, sequence=1),
        _reading(data, timestamp=now + timedelta(minutes=1), sequence=2, pressure=float("inf")),
    ])
    session.commit()

    result = _build(session, data)

    assert result.dataframe["sequence_number"].tolist() == [1, 3]
    assert result.summary.excluded_invalid == 1


def test_empty_result_and_invalid_selection_parameters_are_controlled(dataset_db) -> None:
    session, data = dataset_db
    now = data["now"]

    result = _build(session, data)

    assert result.dataframe.empty and result.summary.included == 0
    with pytest.raises(ValueError, match="earlier"):
        _build(session, data, start_time=now, end_time=now - timedelta(minutes=1))
    with pytest.raises(ValueError, match="source_types"):
        _build(session, data, source_types=[])
