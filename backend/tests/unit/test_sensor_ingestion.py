"""Validation coverage for CSV and manual raw-sensor ingestion."""

import pytest

from app.exceptions import BusinessRuleError
from app.schemas.sensor_ingestion import ManualSensorReading
from app.services.sensor_ingestion_service import SensorIngestionService


def test_manual_pump_requires_raw_operational_measurements() -> None:
    with pytest.raises(ValueError, match="debi, basınç ve motor akımı"):
        ManualSensorReading.model_validate(
            {"timestamp": "2026-08-13T10:00:00Z", "pump_id": 4, "flow_rate": 10}
        )


def test_csv_reports_turkish_missing_column_error_before_persisting() -> None:
    with pytest.raises(BusinessRuleError, match="zorunlu kolonlar eksik"):
        SensorIngestionService(object()).ingest_csv(  # type: ignore[arg-type]
            station_id=1,
            family="pump",
            content="timestamp,pump_id,flow_rate\n2026-08-13T10:00:00Z,4,12\n",
        )


def test_csv_rejects_invalid_rows_without_faking_accepted_data() -> None:
    service = SensorIngestionService(object())  # type: ignore[arg-type]
    result = service.ingest_csv(
        station_id=1,
        family="tank",
        content=(
            "timestamp,tank_id,tank_level,true_tank_level,temperature,water_level\n"
            "not-a-time,2,500,501,20,1\n"
        ),
    )

    assert result.total_rows == 1
    assert result.accepted_rows == 0
    assert result.rejected_rows == 1
    assert result.errors[0].startswith("Satır 2:")
