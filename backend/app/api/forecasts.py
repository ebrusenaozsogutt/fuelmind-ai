"""Production demand forecast endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.forecast import Forecast
from app.models.model_version import ModelVersion
from app.models.user import User
from app.ml.demand_model import SevenDayMovingAverageBaseline
from app.ml.demand_preprocessing import DemandForecastDatasetBuilder
from app.services.forecast_generation_service import (
    DemandForecastArtifactError,
    DemandForecastError,
    ForecastGenerationService,
)

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.post("/generate")
def generate(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    fuel_type_id: int | None = None,
    horizon_days: int = Query(default=7, ge=1, le=7),
) -> list[dict[str, object]]:
    try:
        rows = ForecastGenerationService(db).generate(station_id, fuel_type_id, horizon_days)
    except DemandForecastArtifactError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except DemandForecastError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return [_row(row) for row in rows]


@router.get("/latest")
def latest(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    fuel_type_id: int | None = None,
) -> list[dict[str, object]]:
    statement = select(Forecast).where(Forecast.station_id == station_id)
    if fuel_type_id is not None:
        statement = statement.where(Forecast.fuel_type_id == fuel_type_id)
    rows = list(db.scalars(statement.order_by(Forecast.created_at.desc(), Forecast.id.desc())).all())
    # A generation has no separate id in the existing schema.  For each series,
    # select the model/version with the most recently persisted row, then return
    # its chronological seven-day horizon without deleting historical forecasts.
    chosen: dict[int, str] = {}
    for row in rows:
        chosen.setdefault(row.fuel_type_id, row.model_version)
    selected = [row for row in rows if chosen.get(row.fuel_type_id) == row.model_version]
    return [_row(row) for row in sorted(selected, key=lambda item: (item.fuel_type_id, item.forecast_date))]


@router.get("/performance")
def performance(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> dict[str, object] | None:
    row = db.scalar(select(ModelVersion).where(
        ModelVersion.model_type == "demand_xgboost", ModelVersion.is_active.is_(True)
    ))
    if row is None:
        fallback = db.scalar(select(ModelVersion).where(ModelVersion.model_type == "demand_xgboost").order_by(ModelVersion.trained_at.desc()))
        if fallback is None:
            return None
        metrics = (fallback.metadata_json or {}).get("baseline_metrics")
        if not isinstance(metrics, dict):
            evaluation = SevenDayMovingAverageBaseline().evaluate(DemandForecastDatasetBuilder(db).build().feature_dataframe)
            metrics = {"mae": evaluation.mae, "rmse": evaluation.rmse, "mape": evaluation.mape, "training_row_count": evaluation.train_row_count}
        return {"winner": "baseline", "model_type": "seven_day_moving_average", "model_version": "baseline:seven_day_moving_average", **metrics}
    return {
        "winner": "xgboost",
        "model_version": row.version, "model_type": row.model_type, "mae": row.mae,
        "rmse": row.rmse, "mape": row.mape, "training_start_date": row.training_start_date,
        "training_end_date": row.training_end_date, "training_row_count": row.training_row_count,
        "trained_at": row.trained_at,
    }


def _row(row: Forecast) -> dict[str, object]:
    return {
        "date": row.forecast_date, "forecast_date": row.forecast_date,
        "station_id": row.station_id, "fuel_type_id": row.fuel_type_id,
        "fuel_type": row.fuel_type.name,
        "predicted_demand": row.predicted_demand, "lower_bound": row.lower_bound,
        "upper_bound": row.upper_bound, "confidence_score": row.confidence_score,
        "model_version": row.model_version,
    }
