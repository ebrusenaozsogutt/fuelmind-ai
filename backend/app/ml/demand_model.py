"""Historical evaluation for the demand-forecast moving-average baseline.

No model artifact is trained or persisted here.  The baseline uses the
preprocessing pipeline's leakage-safe ``rolling_mean_7`` feature, which is the
mean of the seven real demand values immediately preceding each date.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite, sqrt

import numpy as np
import pandas as pd

from app.ml.demand_preprocessing import IDENTIFIER_COLUMNS, TARGET_COLUMN

BASELINE_MODEL_NAME = "seven_day_moving_average"
BASELINE_MODEL_TYPE = "baseline"
SPLIT_RATIO = 0.80
MINIMUM_TRAIN_ROWS = 7


class InsufficientDemandDataError(ValueError):
    """Raised when one demand series cannot form a meaningful evaluation."""


@dataclass(frozen=True)
class DemandForecastMetrics:
    """Metrics in litres, except ``mape`` which is a human-readable percent."""

    mae: float
    rmse: float
    mape: float | None
    mape_excluded_zero_actual_count: int


@dataclass(frozen=True)
class DemandModelEvaluation:
    """Reusable historical-evaluation contract for baseline and later models."""

    model_name: str
    model_type: str
    train_row_count: int
    test_row_count: int
    mae: float
    rmse: float
    mape: float | None
    mape_excluded_zero_actual_count: int
    predictions: pd.DataFrame
    series_evaluations: tuple["DemandModelEvaluation", ...] = ()
    station_id: int | None = None
    fuel_type_id: int | None = None


PREDICTION_COLUMNS = (
    "date", "station_id", "fuel_type_id", "actual_demand", "predicted_demand",
    "error", "absolute_error",
)


def evaluate_demand_metrics(actual: pd.Series | np.ndarray, predicted: pd.Series | np.ndarray) -> DemandForecastMetrics:
    """Calculate MAE/RMSE and safe percentage MAPE without infinity."""

    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)
    if actual_values.shape != predicted_values.shape or actual_values.size == 0:
        raise ValueError("actual and predicted must be non-empty arrays of equal length.")
    if not np.isfinite(actual_values).all() or not np.isfinite(predicted_values).all():
        raise ValueError("actual and predicted values must be finite.")
    errors = actual_values - predicted_values
    nonzero_actual = actual_values != 0
    mape = (
        float(np.mean(np.abs(errors[nonzero_actual] / actual_values[nonzero_actual])) * 100)
        if nonzero_actual.any()
        else None
    )
    return DemandForecastMetrics(
        mae=float(np.mean(np.abs(errors))),
        rmse=float(sqrt(np.mean(np.square(errors)))),
        mape=mape,
        mape_excluded_zero_actual_count=int((~nonzero_actual).sum()),
    )


class SevenDayMovingAverageBaseline:
    """Evaluate one-step daily forecasts per station/fuel-type series.

    Each test date uses its own prior-seven-day aggregate from preprocessing.
    Therefore a later test target cannot affect an earlier prediction, while a
    newly observed prior day is available for the following day's forecast.
    """

    model_name = BASELINE_MODEL_NAME
    model_type = BASELINE_MODEL_TYPE

    def evaluate(self, feature_dataframe: pd.DataFrame) -> DemandModelEvaluation:
        self._validate_dataframe(feature_dataframe)
        evaluations: list[DemandModelEvaluation] = []
        for (station_id, fuel_type_id), series in feature_dataframe.groupby(
            ["station_id", "fuel_type_id"], sort=True
        ):
            train, test = self.time_split(series)
            predictions = self._predict_test(test)
            metrics = evaluate_demand_metrics(
                predictions["actual_demand"], predictions["predicted_demand"]
            )
            evaluations.append(DemandModelEvaluation(
                model_name=self.model_name, model_type=self.model_type,
                train_row_count=len(train), test_row_count=len(test),
                mae=metrics.mae, rmse=metrics.rmse, mape=metrics.mape,
                mape_excluded_zero_actual_count=metrics.mape_excluded_zero_actual_count,
                predictions=predictions, station_id=int(station_id), fuel_type_id=int(fuel_type_id),
            ))
        if not evaluations:
            raise InsufficientDemandDataError("No model-ready demand series are available.")
        combined = pd.concat([item.predictions for item in evaluations], ignore_index=True)
        combined = combined.sort_values(list(IDENTIFIER_COLUMNS), kind="stable").reset_index(drop=True)
        metrics = evaluate_demand_metrics(combined["actual_demand"], combined["predicted_demand"])
        return DemandModelEvaluation(
            model_name=self.model_name, model_type=self.model_type,
            train_row_count=sum(item.train_row_count for item in evaluations),
            test_row_count=len(combined), mae=metrics.mae, rmse=metrics.rmse, mape=metrics.mape,
            mape_excluded_zero_actual_count=metrics.mape_excluded_zero_actual_count,
            predictions=combined, series_evaluations=tuple(evaluations),
        )

    @staticmethod
    def time_split(series: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        ordered = series.sort_values("date", kind="stable").reset_index(drop=True)
        split_index = floor(len(ordered) * SPLIT_RATIO)
        if split_index < MINIMUM_TRAIN_ROWS or len(ordered) - split_index < 1:
            raise InsufficientDemandDataError(
                "A demand series needs at least seven train rows and one test row after warm-up."
            )
        return ordered.iloc[:split_index].copy(), ordered.iloc[split_index:].copy()

    @staticmethod
    def _predict_test(test: pd.DataFrame) -> pd.DataFrame:
        predicted = test["rolling_mean_7"].astype(float).clip(lower=0.0)
        if not predicted.map(isfinite).all():
            raise InsufficientDemandDataError("Test rows require finite rolling_mean_7 values.")
        actual = test[TARGET_COLUMN].astype(float)
        result = test.loc[:, list(IDENTIFIER_COLUMNS)].copy()
        result["actual_demand"] = actual
        result["predicted_demand"] = predicted
        result["error"] = actual - predicted
        result["absolute_error"] = result["error"].abs()
        return result.loc[:, list(PREDICTION_COLUMNS)].reset_index(drop=True)

    @staticmethod
    def _validate_dataframe(frame: pd.DataFrame) -> None:
        required = {*IDENTIFIER_COLUMNS, TARGET_COLUMN, "rolling_mean_7"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Demand feature dataset is missing columns: {sorted(missing)}")
