"""Validated persistence for manual and CSV-originated raw sensor data."""

from __future__ import annotations

import csv
import io

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.pump import Pump
from app.models.sensor_reading import SensorReading
from app.models.station import Station
from app.models.tank import Tank
from app.schemas.sensor_ingestion import ManualSensorReading, SensorImportResult
from app.utils.enums import SourceType


CSV_REQUIRED_COLUMNS = {
    "pump": ("timestamp", "pump_id", "flow_rate", "pressure", "motor_current"),
    "tank": ("timestamp", "tank_id", "tank_level", "true_tank_level", "temperature", "water_level"),
}


class SensorIngestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ingest_manual(self, *, station_id: int, rows: list[ManualSensorReading]) -> SensorImportResult:
        return self._persist(station_id=station_id, rows=rows, source_type=SourceType.MANUAL)

    def ingest_csv(self, *, station_id: int, family: str, content: str) -> SensorImportResult:
        if family not in CSV_REQUIRED_COLUMNS:
            raise BusinessRuleError("Model ailesi pompa veya tank olmalıdır.")
        reader = csv.DictReader(io.StringIO(content))
        columns = set(reader.fieldnames or ())
        missing = [name for name in CSV_REQUIRED_COLUMNS[family] if name not in columns]
        if missing:
            raise BusinessRuleError(
                "CSV dosyasında zorunlu kolonlar eksik: " + ", ".join(missing)
            )
        parsed: list[ManualSensorReading] = []
        errors: list[str] = []
        raw_rows = list(reader)
        for index, row in enumerate(raw_rows, start=2):
            try:
                parsed.append(ManualSensorReading.model_validate({
                    key: value if value != "" else None for key, value in row.items()
                }))
            except ValidationError as exc:
                errors.append(f"Satır {index}: {exc.errors()[0]['msg']}")
        if not parsed:
            return SensorImportResult(
                total_rows=len(raw_rows), accepted_rows=0,
                rejected_rows=len(errors), errors=errors[:50],
            )
        accepted = self._persist(station_id=station_id, rows=parsed, source_type=SourceType.CSV_IMPORT)
        return SensorImportResult(
            total_rows=len(raw_rows), accepted_rows=accepted.accepted_rows,
            rejected_rows=len(errors), errors=errors[:50],
        )

    def _persist(
        self, *, station_id: int, rows: list[ManualSensorReading], source_type: SourceType
    ) -> SensorImportResult:
        if self.db.get(Station, station_id) is None:
            raise NotFoundError("İstasyon bulunamadı.")
        values: list[SensorReading] = []
        for index, row in enumerate(rows, start=1):
            tank_id = row.tank_id
            if row.pump_id is not None:
                pump = self.db.get(Pump, row.pump_id)
                if pump is None or pump.station_id != station_id:
                    raise BusinessRuleError(f"Satır {index}: Pompa bu istasyona ait değil.")
                tank_id = tank_id or pump.tank_id
            if tank_id is not None:
                tank = self.db.get(Tank, tank_id)
                if tank is None or tank.station_id != station_id:
                    raise BusinessRuleError(f"Satır {index}: Tank bu istasyona ait değil.")
            values.append(SensorReading(
                station_id=station_id, tank_id=tank_id, pump_id=row.pump_id,
                reading_timestamp=row.timestamp, tank_level=row.tank_level,
                true_tank_level=row.true_tank_level, temperature=row.temperature,
                water_level=row.water_level, flow_rate=row.flow_rate, pressure=row.pressure,
                motor_current=row.motor_current, pump_temperature=row.pump_temperature,
                error_count=row.error_count, working_duration=row.working_duration,
                data_quality_score=row.data_quality_score, quality_flags_json=[],
                is_anomaly=False, source_type=source_type,
            ))
        try:
            self.db.add_all(values)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return SensorImportResult(total_rows=len(rows), accepted_rows=len(rows), rejected_rows=0)
