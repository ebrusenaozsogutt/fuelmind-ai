"""Production-only, leakage-safe recursive demand forecast generation."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.ml.demand_preprocessing import FEATURE_COLUMNS, TARGET_COLUMN, DemandForecastDatasetBuilder
from app.ml.demand_model import SevenDayMovingAverageBaseline
from app.ml.demand_xgboost import DemandXGBoostArtifact, XGBOOST_MODEL_TYPE
from app.models.forecast import Forecast
from app.models.model_version import ModelVersion
from app.services.demand_training_service import DEMAND_MODEL_FAMILY, DemandTrainingService

HORIZON_DAYS = 7
RESIDUAL_QUANTILE = 0.90
HORIZON_MARGIN_INCREMENT = 0.05
CONFIDENCE_WEIGHTS = {"performance": 0.55, "data_amount": 0.25, "model_age": 0.20}
CONFIDENCE_TRAINING_ROWS_FULL = 100
CONFIDENCE_AGE_DAYS_FULL = 90
CONFIDENCE_HORIZON_DECAY = 0.03


class DemandForecastError(ValueError):
    """A controlled production-demand forecast error."""


class DemandForecastUnavailableError(DemandForecastError):
    """No active artifact is available for the requested demand series."""


class DemandForecastArtifactError(DemandForecastError):
    """The selected active artifact cannot safely be loaded."""


class ForecastGenerationService:
    """Load a trained artifact and produce exactly seven future daily rows."""

    def __init__(self, db: Session, *, registry_root: Path | None = None) -> None:
        self.db = db
        self.root = (registry_root or settings.MODEL_REGISTRY_ROOT).resolve()

    def generate(self, station_id: int, fuel_type_id: int | None = None, horizon_days: int = HORIZON_DAYS) -> list[Forecast]:
        if horizon_days != HORIZON_DAYS:
            raise DemandForecastError("Only a seven-day forecast horizon is supported.")
        dataset = DemandForecastDatasetBuilder(self.db).build(station_id=station_id)
        daily = dataset.daily_dataframe
        if fuel_type_id is not None:
            daily = daily[daily.fuel_type_id == fuel_type_id]
        if daily.empty:
            raise DemandForecastUnavailableError("No historical demand data is available for this station/fuel scope.")

        record = self._active_record()
        if record is None:
            return self._generate_baseline(dataset, station_id, fuel_type_id)
        artifact = self._load_artifact(record)
        results: list[Forecast] = []
        for (sid, fid), group in daily.groupby(["station_id", "fuel_type_id"], sort=True):
            key = f"{sid}:{fid}"
            model = artifact.models.get(key)  # Exact scope; never cross fuel types.
            if model is None:
                raise DemandForecastUnavailableError(f"Active demand model has no scope for series {key}.")
            history = group.sort_values("date")[TARGET_COLUMN].astype(float).tolist()
            if len(history) < 14:
                raise DemandForecastUnavailableError("At least 14 daily values are required for forecast inference.")
            results.extend(self._generate_series(record, model, int(sid), int(fid), group.date.max(), history))
        self.db.commit()
        return sorted(results, key=lambda row: (row.station_id, row.fuel_type_id, row.forecast_date))

    def _active_record(self) -> ModelVersion | None:
        record = self.db.scalar(select(ModelVersion).where(
            ModelVersion.model_type == XGBOOST_MODEL_TYPE,
            ModelVersion.model_family == DEMAND_MODEL_FAMILY,
            ModelVersion.is_active.is_(True),
        ))
        return record

    def _generate_baseline(self, dataset: object, station_id: int, fuel_type_id: int | None) -> list[Forecast]:
        evaluation = SevenDayMovingAverageBaseline().evaluate(dataset.feature_dataframe)
        daily = dataset.daily_dataframe
        if fuel_type_id is not None:
            daily = daily[daily.fuel_type_id == fuel_type_id]
        margin = float(np.quantile(evaluation.predictions["absolute_error"], RESIDUAL_QUANTILE))
        results: list[Forecast] = []
        for (sid, fid), group in daily.groupby(["station_id", "fuel_type_id"], sort=True):
            history = group.sort_values("date")[TARGET_COLUMN].astype(float).tolist()
            if len(history) < 7:
                raise DemandForecastUnavailableError("At least seven daily values are required for baseline inference.")
            latest = group.date.max()
            for step in range(1, HORIZON_DAYS + 1):
                prediction = max(0.0, float(np.mean(history[-7:])))
                history.append(prediction)
                spread = margin * self.horizon_multiplier(step)
                moment = latest + timedelta(days=step)
                row = self.db.scalar(select(Forecast).where(
                    Forecast.station_id == sid, Forecast.fuel_type_id == fid,
                    Forecast.forecast_date == moment,
                    Forecast.model_version == "baseline:seven_day_moving_average",
                ))
                if row is None:
                    row = Forecast(
                        station_id=int(sid), fuel_type_id=int(fid), forecast_date=moment,
                        predicted_demand=Decimal(str(prediction)), lower_bound=Decimal(str(max(0.0, prediction - spread))),
                        upper_bound=Decimal(str(prediction + spread)),
                        confidence_score=Decimal(str(self.baseline_confidence(evaluation.mae, evaluation.train_row_count, float(np.mean(history[:-1])), step))),
                        model_version="baseline:seven_day_moving_average",
                    )
                    self.db.add(row)
                results.append(row)
        self.db.commit()
        return sorted(results, key=lambda row: (row.station_id, row.fuel_type_id, row.forecast_date))

    def _load_artifact(self, record: ModelVersion) -> DemandXGBoostArtifact:
        path = (self.root.parent / record.file_path).resolve()
        try:
            artifact = DemandTrainingService.load_artifact(path)
        except Exception as exc:  # joblib may surface several pickle/deserialization types.
            raise DemandForecastArtifactError(f"Active demand artifact '{record.version}' could not be loaded.") from exc
        if tuple(artifact.feature_columns) != tuple(FEATURE_COLUMNS):
            raise DemandForecastArtifactError("Active demand artifact does not match the production feature contract.")
        return artifact

    def _generate_series(self, record: ModelVersion, model: object, station_id: int, fuel_type_id: int, latest: date, history: list[float]) -> list[Forecast]:
        base_margin, mean_demand = self.residual_margin(record), float(np.mean(history))
        rows: list[Forecast] = []
        for step in range(1, HORIZON_DAYS + 1):
            forecast_date = latest + timedelta(days=step)
            features = self._feature(forecast_date, history)
            prediction = max(0.0, float(model.predict(features.loc[:, list(FEATURE_COLUMNS)])[0]))
            history.append(prediction)  # Required recursive input for the next day.
            margin = base_margin * self.horizon_multiplier(step)
            lower, upper = max(0.0, prediction - margin), prediction + margin
            row = self.db.scalar(select(Forecast).where(
                Forecast.station_id == station_id, Forecast.fuel_type_id == fuel_type_id,
                Forecast.forecast_date == forecast_date, Forecast.model_version == record.version,
            ))
            if row is None:
                row = Forecast(
                    station_id=station_id, fuel_type_id=fuel_type_id, forecast_date=forecast_date,
                    predicted_demand=Decimal(str(prediction)), lower_bound=Decimal(str(lower)),
                    upper_bound=Decimal(str(upper)),
                    confidence_score=Decimal(str(self.confidence_score(record, mean_demand, step))),
                    model_version=record.version,
                )
                self.db.add(row)
            rows.append(row)
        return rows

    @staticmethod
    def _feature(moment: date, history: list[float]) -> pd.DataFrame:
        values = np.asarray(history, dtype=float)
        data = {
            "day_of_week": moment.weekday(), "day_of_month": moment.day, "month": moment.month,
            "is_weekend": int(moment.weekday() >= 5), "lag_1": values[-1], "lag_2": values[-2],
            "lag_7": values[-7], "lag_14": values[-14], "rolling_mean_3": values[-3:].mean(),
            "rolling_mean_7": values[-7:].mean(), "rolling_mean_14": values[-14:].mean(),
            "rolling_std_7": values[-7:].std(ddof=1),
        }
        return pd.DataFrame([data], columns=list(FEATURE_COLUMNS))

    @staticmethod
    def residual_margin(record: ModelVersion) -> float:
        """90th percentile absolute historical residual, stored during training."""
        value = (record.metadata_json or {}).get("residual_abs_p90")
        return max(0.0, float(record.mae if value is None else value or 0.0))

    @staticmethod
    def horizon_multiplier(step: int) -> float:
        return 1.0 + (step - 1) * HORIZON_MARGIN_INCREMENT

    @staticmethod
    def confidence_score(record: ModelVersion, mean_demand: float, step: int, *, generated_at: datetime | None = None) -> float:
        """Deterministic weighted score, followed by monotonic horizon decay."""
        performance = max(0.0, min(1.0, 1 - float(record.mae or 0) / max(mean_demand, 1.0)))
        data_amount = min(1.0, max(0.0, record.training_row_count / CONFIDENCE_TRAINING_ROWS_FULL))
        now = generated_at or datetime.now(timezone.utc)
        trained = record.trained_at if record.trained_at.tzinfo else record.trained_at.replace(tzinfo=timezone.utc)
        age = max(0.0, (now - trained).total_seconds() / 86400)
        model_age = max(0.0, 1 - age / CONFIDENCE_AGE_DAYS_FULL)
        base = (CONFIDENCE_WEIGHTS["performance"] * performance + CONFIDENCE_WEIGHTS["data_amount"] * data_amount + CONFIDENCE_WEIGHTS["model_age"] * model_age)
        return round(max(0.0, min(100.0, 100 * base * (1 - (step - 1) * CONFIDENCE_HORIZON_DECAY))), 2)

    @staticmethod
    def baseline_confidence(mae: float, training_rows: int, mean_demand: float, step: int) -> float:
        performance = max(0.0, min(1.0, 1 - mae / max(mean_demand, 1.0)))
        amount = min(1.0, max(0.0, training_rows / CONFIDENCE_TRAINING_ROWS_FULL))
        return round(max(0.0, min(100.0, 100 * (0.7 * performance + 0.3 * amount) * (1 - (step - 1) * CONFIDENCE_HORIZON_DECAY))), 2)
