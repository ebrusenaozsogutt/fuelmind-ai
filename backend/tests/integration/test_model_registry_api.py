"""HTTP and real-pipeline acceptance coverage for Stage 8.7."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_active_user
from app.database import Base, get_db
from app.main import app
from app.ml import model_registry
from app.models.model_version import ModelVersion
from app.models.sensor_reading import SensorReading
from app.models.simulation_run import SimulationRun
from app.models.simulation_scenario import SimulationScenario
from app.models.station import Station
from app.utils.enums import SourceType, UserRole

_TABLES = [
    Station.__table__,
    SimulationRun.__table__,
    SimulationScenario.__table__,
    SensorReading.__table__,
    ModelVersion.__table__,
]


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_: JSONB, __, **___) -> str:
    return "JSON"


@pytest.fixture
def registry_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    project_root = tmp_path / "project"
    monkeypatch.setattr(
        model_registry.settings,
        "MODEL_REGISTRY_ROOT",
        project_root / "trained_models",
    )
    session = factory()
    station = Station(
        code="REG-1", name="Registry", city="Istanbul", district="Test", address="Test"
    )
    session.add(station)
    session.flush()
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    session.add_all(
        [
            SensorReading(
                station_id=station.id,
                pump_id=1,
                tank_id=1,
                simulation_run_id=None,
                sequence_number=index + 1,
                reading_timestamp=start + timedelta(minutes=5 * index),
                flow_rate=Decimal(str(10 + index / 10)),
                pressure=Decimal(str(2 + index / 100)),
                motor_current=Decimal(str(8 + index / 50)),
                pump_temperature=Decimal(str(25 + index / 20)),
                error_count=0,
                working_duration=Decimal(str(index / 12)),
                data_quality_score=Decimal("99"),
                quality_flags_json=[],
                source_type=SourceType.SIMULATION,
            )
            for index in range(48)
        ]
    )
    session.commit()
    app.dependency_overrides[get_db] = lambda: factory()
    app.dependency_overrides[get_current_active_user] = lambda: type(
        "Admin", (), {"role": UserRole.ADMIN, "is_active": True}
    )()
    try:
        with TestClient(app) as client:
            yield client, factory, project_root, station.id
    finally:
        model_registry.AnomalyModelRegistry.invalidate_cache()
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()


def test_real_training_pipeline_creates_db_artifact_and_list_response(registry_api) -> None:
    client, factory, project_root, station_id = registry_api
    response = client.post(
        "/api/ml/train-anomaly-model",
        json={
            "station_id": station_id,
            "model_family": "pump",
            "source_types": ["SIMULATION"],
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["version"] == "v0001"
    assert payload["model_type"] == "isolation_forest"
    assert payload["model_family"] == "pump"
    assert payload["training_row_count"] >= 8
    assert payload["training_start_date"] == "2026-08-01"
    assert payload["training_end_date"] == "2026-08-01"
    assert payload["feature_count"] == 20
    assert payload["training_outlier_fraction"] is not None
    assert payload["normal_false_positive_rate"] is None
    assert payload["scenario_detection_count"] is None
    assert payload["validation_status"] is None
    assert payload["is_active"] is True
    assert payload["artifact_available"] is True
    assert "model" in payload["training_diagnostics"]
    assert not Path(payload["artifact_file_name"]).is_absolute()

    with factory() as session:
        record = session.get(ModelVersion, payload["id"])
        assert record is not None
        assert (project_root / record.file_path).is_file()
        session.add(
            SensorReading(
                station_id=station_id,
                pump_id=1,
                tank_id=1,
                reading_timestamp=datetime(2026, 8, 2, tzinfo=timezone.utc),
                flow_rate=Decimal("11"),
                pressure=Decimal("2"),
                motor_current=Decimal("8"),
                pump_temperature=Decimal("27"),
                error_count=0,
                working_duration=Decimal("5"),
                data_quality_score=Decimal("99"),
                quality_flags_json=[],
                source_type=SourceType.SIMULATION,
            )
        )
        session.commit()
    listed = client.get("/api/models")
    assert listed.status_code == 200
    listed_model = listed.json()[0]
    assert listed_model["id"] == payload["id"]
    assert listed_model["latest_sensor_reading_at"].startswith("2026-08-02")
    assert listed_model["new_sensor_rows_since_training"] == 1

    second = client.post(
        "/api/ml/train-anomaly-model",
        json={"station_id": station_id, "model_family": "pump"},
    )
    assert second.status_code == 201
    assert second.json()["version"] == "v0002"
    assert second.json()["is_active"] is False
    activated = client.patch(f"/api/models/{second.json()['id']}/activate")
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True
    active_rows = [item for item in client.get("/api/models").json() if item["is_active"]]
    assert [item["version"] for item in active_rows] == ["v0002"]

    third = client.post(
        "/api/ml/train-anomaly-model",
        json={"station_id": station_id, "model_family": "pump"},
    )
    assert third.status_code == 201
    assert third.json()["version"] == "v0003"
    assert third.json()["is_active"] is False
    versions = client.get("/api/models").json()
    assert {item["version"] for item in versions} == {"v0001", "v0002", "v0003"}
    assert [item["version"] for item in versions if item["is_active"]] == ["v0002"]


def test_activation_requires_admin_and_anonymous_is_unauthorized(registry_api) -> None:
    client, _, _, _ = registry_api
    app.dependency_overrides[get_current_active_user] = lambda: type(
        "Operator", (), {"role": UserRole.OPERATOR, "is_active": True}
    )()
    assert client.patch("/api/models/1/activate").status_code == 403

    app.dependency_overrides.pop(get_current_active_user)
    assert client.patch("/api/models/1/activate").status_code == 401


def test_empty_training_dataset_is_a_safe_business_error(registry_api) -> None:
    client, _, _, station_id = registry_api
    response = client.post(
        "/api/ml/train-anomaly-model",
        json={
            "station_id": station_id,
            "model_family": "pump",
            "end_time": "2020-01-01T00:00:00Z",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"
