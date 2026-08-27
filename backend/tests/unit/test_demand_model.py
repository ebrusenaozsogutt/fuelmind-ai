"""Stage 12.4/12.6/12.7 baseline historical-evaluation coverage."""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.ml.demand_model import (
    InsufficientDemandDataError,
    SevenDayMovingAverageBaseline,
    evaluate_demand_metrics,
)
from app.ml.demand_preprocessing import TARGET_COLUMN


def series(rows: int, *, station_id: int = 1, fuel_type_id: int = 1) -> pd.DataFrame:
    values = list(range(10, 10 + rows))
    return pd.DataFrame({
        "date": [date(2026, 1, 1) + timedelta(days=index) for index in range(rows)],
        "station_id": station_id,
        "fuel_type_id": fuel_type_id,
        TARGET_COLUMN: values,
        "rolling_mean_7": [40.0] * rows,
    })


def test_baseline_math_uses_prior_seven_day_average() -> None:
    frame = series(10)
    frame.loc[:, "rolling_mean_7"] = [float("nan")] * 7 + [40.0, 50.0, 60.0]
    predictions = SevenDayMovingAverageBaseline()._predict_test(frame.iloc[7:8])
    assert predictions.iloc[0].predicted_demand == 40.0


def test_day_target_does_not_change_its_prediction() -> None:
    frame = series(20)
    baseline = SevenDayMovingAverageBaseline()
    original = baseline.evaluate(frame).predictions
    changed = frame.copy()
    changed.loc[changed.index[-1], TARGET_COLUMN] = 99999
    reevaluated = baseline.evaluate(changed).predictions
    assert original.iloc[-1].predicted_demand == reevaluated.iloc[-1].predicted_demand


def test_split_is_chronological_per_series_without_shuffle() -> None:
    train, test = SevenDayMovingAverageBaseline.time_split(series(100).sample(frac=1, random_state=4))
    assert len(train) == 80
    assert len(test) == 20
    assert train.date.max() < test.date.min()


def test_series_isolation_and_complete_evaluation_contract() -> None:
    evaluation = SevenDayMovingAverageBaseline().evaluate(pd.concat([
        series(20), series(20, station_id=2, fuel_type_id=2),
    ], ignore_index=True))
    assert evaluation.model_name == "seven_day_moving_average"
    assert evaluation.model_type == "baseline"
    assert evaluation.train_row_count == 32
    assert evaluation.test_row_count == 8
    assert len(evaluation.series_evaluations) == 2
    assert set(evaluation.predictions.columns) == {
        "date", "station_id", "fuel_type_id", "actual_demand", "predicted_demand", "error", "absolute_error",
    }
    assert set(evaluation.predictions.station_id) == {1, 2}


def test_short_dataset_is_rejected_clearly() -> None:
    with pytest.raises(InsufficientDemandDataError, match="seven train rows"):
        SevenDayMovingAverageBaseline().evaluate(series(8))


def test_metrics_are_correct_and_mape_is_percentage() -> None:
    metrics = evaluate_demand_metrics([100, 200], [90, 220])
    assert metrics.mae == 15
    assert metrics.rmse == pytest.approx((250) ** 0.5)
    assert metrics.mape == pytest.approx(10.0)
    assert metrics.mape_excluded_zero_actual_count == 0


def test_mape_excludes_zero_actual_and_all_zero_is_not_computable() -> None:
    mixed = evaluate_demand_metrics([0, 100], [10, 90])
    assert mixed.mape == pytest.approx(10.0)
    assert mixed.mape_excluded_zero_actual_count == 1
    all_zero = evaluate_demand_metrics([0, 0], [1, 2])
    assert all_zero.mape is None
    assert all_zero.mape_excluded_zero_actual_count == 2


def test_predictions_are_never_negative() -> None:
    frame = series(20)
    frame.loc[:, "rolling_mean_7"] = -4.0
    assert (SevenDayMovingAverageBaseline().evaluate(frame).predictions.predicted_demand >= 0).all()
