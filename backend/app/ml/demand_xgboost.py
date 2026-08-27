"""Deterministic per-series XGBoost evaluation for daily fuel demand."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd
from xgboost import XGBRegressor

from app.ml.demand_model import (
    DemandModelEvaluation,
    InsufficientDemandDataError,
    PREDICTION_COLUMNS,
    SevenDayMovingAverageBaseline,
    evaluate_demand_metrics,
)
from app.ml.demand_preprocessing import FEATURE_COLUMNS, IDENTIFIER_COLUMNS, TARGET_COLUMN

XGBOOST_MODEL_NAME = "xgboost_regressor"
XGBOOST_MODEL_TYPE = "demand_xgboost"
XGBOOST_CONFIG = {
    "objective": "reg:squarederror", "n_estimators": 40, "max_depth": 2,
    "learning_rate": 0.08, "subsample": 1.0, "colsample_bytree": 1.0,
    "random_state": 42, "n_jobs": 1, "verbosity": 0,
}


@dataclass(frozen=True)
class DemandXGBoostArtifact:
    """The minimum information needed to safely reconstruct demand inference."""

    model_type: str
    feature_columns: tuple[str, ...]
    target_column: str
    models: dict[str, XGBRegressor]
    training_end_date: str
    training_row_count: int
    config: dict[str, object]


@dataclass(frozen=True)
class XGBoostEvaluationResult:
    evaluation: DemandModelEvaluation
    artifact: DemandXGBoostArtifact
    feature_importance: tuple[tuple[str, float], ...]


class DemandXGBoostEvaluator:
    """Fit only chronological training rows and evaluate the matching test rows."""

    def __init__(self, *, config: dict[str, object] | None = None) -> None:
        self.config = dict(XGBOOST_CONFIG if config is None else config)

    def evaluate(self, feature_dataframe: pd.DataFrame) -> XGBoostEvaluationResult:
        baseline = SevenDayMovingAverageBaseline()
        baseline._validate_dataframe(feature_dataframe)
        evaluations: list[DemandModelEvaluation] = []
        models: dict[str, XGBRegressor] = {}
        importances: list[pd.Series] = []
        for (station_id, fuel_type_id), series in feature_dataframe.groupby(
            ["station_id", "fuel_type_id"], sort=True
        ):
            train, test = baseline.time_split(series)
            model = XGBRegressor(**self.config)
            model.fit(train.loc[:, list(FEATURE_COLUMNS)], train[TARGET_COLUMN])
            prediction = pd.Series(model.predict(test.loc[:, list(FEATURE_COLUMNS)]), index=test.index)
            predictions = self._prediction_frame(test, prediction)
            metrics = evaluate_demand_metrics(predictions["actual_demand"], predictions["predicted_demand"])
            evaluations.append(DemandModelEvaluation(
                model_name=XGBOOST_MODEL_NAME, model_type=XGBOOST_MODEL_TYPE,
                train_row_count=len(train), test_row_count=len(test), mae=metrics.mae,
                rmse=metrics.rmse, mape=metrics.mape,
                mape_excluded_zero_actual_count=metrics.mape_excluded_zero_actual_count,
                predictions=predictions, station_id=int(station_id), fuel_type_id=int(fuel_type_id),
            ))
            models[f"{station_id}:{fuel_type_id}"] = model
            importances.append(pd.Series(model.feature_importances_, index=FEATURE_COLUMNS))
        if not evaluations:
            raise InsufficientDemandDataError("No model-ready demand series are available.")
        combined = pd.concat([item.predictions for item in evaluations], ignore_index=True).sort_values(
            list(IDENTIFIER_COLUMNS), kind="stable"
        ).reset_index(drop=True)
        metrics = evaluate_demand_metrics(combined["actual_demand"], combined["predicted_demand"])
        evaluation = DemandModelEvaluation(
            model_name=XGBOOST_MODEL_NAME, model_type=XGBOOST_MODEL_TYPE,
            train_row_count=sum(item.train_row_count for item in evaluations), test_row_count=len(combined),
            mae=metrics.mae, rmse=metrics.rmse, mape=metrics.mape,
            mape_excluded_zero_actual_count=metrics.mape_excluded_zero_actual_count,
            predictions=combined, series_evaluations=tuple(evaluations),
        )
        importance = pd.concat(importances, axis=1).mean(axis=1).sort_values(ascending=False)
        artifact = DemandXGBoostArtifact(
            model_type=XGBOOST_MODEL_TYPE, feature_columns=FEATURE_COLUMNS, target_column=TARGET_COLUMN,
            models=models, training_end_date=str(feature_dataframe["date"].max()),
            training_row_count=evaluation.train_row_count, config=self.config,
        )
        return XGBoostEvaluationResult(
            evaluation=evaluation, artifact=artifact,
            feature_importance=tuple((name, float(value)) for name, value in importance.items()),
        )

    @staticmethod
    def _prediction_frame(test: pd.DataFrame, prediction: pd.Series) -> pd.DataFrame:
        if not prediction.map(isfinite).all():
            raise ValueError("XGBoost produced a non-finite prediction.")
        result = test.loc[:, list(IDENTIFIER_COLUMNS)].copy()
        result["actual_demand"] = test[TARGET_COLUMN].astype(float)
        result["predicted_demand"] = prediction.clip(lower=0.0).astype(float)
        result["error"] = result["actual_demand"] - result["predicted_demand"]
        result["absolute_error"] = result["error"].abs()
        return result.loc[:, list(PREDICTION_COLUMNS)].reset_index(drop=True)
