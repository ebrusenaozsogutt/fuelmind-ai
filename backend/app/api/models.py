"""Model-registry and anomaly-training HTTP endpoints."""

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.ml.model_registry import (
    AnomalyModelRegistry,
    ModelArtifactInvalidError,
    ModelArtifactNotFoundError,
)
from app.models.model_version import ModelVersion
from app.models.sensor_reading import SensorReading
from app.models.user import User
from app.schemas.model_registry import (
    AnomalyModelTrainingRead,
    AnomalyModelTrainRequest,
    ModelVersionRead,
)
from app.services.anomaly_training_service import AnomalyTrainingService

router = APIRouter(tags=["models"])


def _read_model(
    record: ModelVersion,
    registry: AnomalyModelRegistry,
    *,
    diagnostics: dict[str, object] | None = None,
    latest_sensor_reading_at: datetime | None = None,
    new_sensor_rows_since_training: int = 0,
) -> ModelVersionRead | AnomalyModelTrainingRead:
    metadata = record.metadata_json or {}
    training_summary = metadata.get("training_summary")
    training_outlier_fraction = (
        training_summary.get("outlier_fraction_on_training")
        if isinstance(training_summary, dict)
        else None
    )
    if training_outlier_fraction is None and registry.artifact_available(record):
        try:
            training_outlier_fraction = (
                registry.load_version(record.id).training_summary.outlier_fraction_on_training
            )
        except (ModelArtifactNotFoundError, ModelArtifactInvalidError):
            training_outlier_fraction = None
    validation = metadata.get("validation")
    validation = validation if isinstance(validation, dict) else {}
    values = {
        "id": record.id,
        "model_type": record.model_type,
        "model_family": record.model_family,
        "version": record.version,
        "trained_at": record.trained_at,
        "training_start_date": record.training_start_date,
        "training_end_date": record.training_end_date,
        "training_row_count": record.training_row_count,
        "feature_count": metadata.get("feature_count"),
        "feature_names": metadata.get("feature_names", []),
        "is_active": record.is_active,
        "artifact_available": registry.artifact_available(record),
        "artifact_file_name": Path(record.file_path).name,
        "artifact_size_bytes": record.artifact_size_bytes,
        "artifact_schema_version": metadata.get("artifact_schema_version"),
        "training_outlier_fraction": training_outlier_fraction,
        "validation_status": validation.get("status"),
        "scenario_detection_count": validation.get("scenario_detection_count"),
        "scenario_total_count": validation.get("scenario_total_count"),
        "normal_false_positive_rate": validation.get("normal_false_positive_rate"),
        "latest_sensor_reading_at": latest_sensor_reading_at,
        "new_sensor_rows_since_training": new_sensor_rows_since_training,
    }
    if diagnostics is not None:
        return AnomalyModelTrainingRead(
            **values, training_diagnostics=diagnostics
        )
    return ModelVersionRead(**values)


@router.get("/models", response_model=list[ModelVersionRead])
def list_models(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[ModelVersionRead]:
    registry = AnomalyModelRegistry(db)
    records = registry.list_versions()
    latest = db.scalar(select(func.max(SensorReading.reading_timestamp)))
    counts = _new_sensor_counts(db, {record.training_end_date for record in records})
    return [
        _read_model(
            record,
            registry,
            latest_sensor_reading_at=latest,
            new_sensor_rows_since_training=counts[record.training_end_date],
        )
        for record in records
    ]


@router.patch("/models/{version_id}/activate", response_model=ModelVersionRead)
def activate_model(
    version_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> ModelVersionRead:
    registry = AnomalyModelRegistry(db)
    record = registry.activate(version_id)
    latest = db.scalar(select(func.max(SensorReading.reading_timestamp)))
    count = _new_sensor_counts(db, {record.training_end_date})[
        record.training_end_date
    ]
    return _read_model(
        record,
        registry,
        latest_sensor_reading_at=latest,
        new_sensor_rows_since_training=count,
    )


@router.post(
    "/ml/train-anomaly-model",
    response_model=AnomalyModelTrainingRead,
    status_code=status.HTTP_201_CREATED,
)
def train_anomaly_model(
    payload: AnomalyModelTrainRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> AnomalyModelTrainingRead:
    result = AnomalyTrainingService(db).train(payload)
    registry = AnomalyModelRegistry(db)
    record = result.registry_result.model_version
    return _read_model(
        record,
        registry,
        diagnostics=result.diagnostics,
        latest_sensor_reading_at=db.scalar(
            select(func.max(SensorReading.reading_timestamp))
        ),
        new_sensor_rows_since_training=_new_sensor_counts(
            db, {record.training_end_date}
        )[record.training_end_date],
    )


def _new_sensor_counts(
    db: Session, training_end_dates: set[date]
) -> dict[date, int]:
    counts: dict[date, int] = {}
    for end_date in training_end_dates:
        after_training = datetime.combine(
            end_date + timedelta(days=1), time.min, tzinfo=timezone.utc
        )
        counts[end_date] = int(
            db.scalar(
                select(func.count(SensorReading.id)).where(
                    SensorReading.reading_timestamp >= after_training
                )
            )
            or 0
        )
    return counts
