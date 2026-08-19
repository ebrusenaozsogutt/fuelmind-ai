"""Manual and CSV ingestion endpoints for real model-training sources."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.database import get_db
from app.exceptions import BusinessRuleError
from app.models.user import User
from app.schemas.sensor_ingestion import ManualSensorIngestRequest, SensorImportResult
from app.services.sensor_ingestion_service import CSV_REQUIRED_COLUMNS, SensorIngestionService

router = APIRouter(prefix="/sensor-readings", tags=["sensor-readings"])


@router.get("/csv-contract/{model_family}")
def csv_contract(model_family: Literal["pump", "tank"]) -> dict[str, list[str]]:
    return {"required_columns": list(CSV_REQUIRED_COLUMNS[model_family])}


@router.post("/manual", response_model=SensorImportResult)
def ingest_manual(
    payload: ManualSensorIngestRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> SensorImportResult:
    return SensorIngestionService(db).ingest_manual(
        station_id=payload.station_id, rows=payload.rows
    )


@router.post("/csv", response_model=SensorImportResult)
async def ingest_csv(
    station_id: Annotated[int, Form(gt=0)],
    model_family: Annotated[Literal["pump", "tank"], Form()],
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> SensorImportResult:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise BusinessRuleError("Lütfen .csv uzantılı bir dosya seçin.")
    try:
        content = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BusinessRuleError("CSV dosyası UTF-8 kodlamalı olmalıdır.") from exc
    return SensorIngestionService(db).ingest_csv(
        station_id=station_id, family=model_family, content=content
    )
