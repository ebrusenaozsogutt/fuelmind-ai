"""Stage 12.5 XGBoost evaluation tests."""

import pandas as pd
import pytest

from app.ml.demand_model import SevenDayMovingAverageBaseline
from app.ml.demand_preprocessing import FEATURE_COLUMNS, TARGET_COLUMN
from app.ml.demand_xgboost import DemandXGBoostEvaluator
from app.services.demand_training_service import select_demand_winner
from tests.unit.test_demand_model import series


def feature_series(rows: int = 30, *, station_id: int = 1, fuel_type_id: int = 1) -> pd.DataFrame:
    frame = series(rows, station_id=station_id, fuel_type_id=fuel_type_id)
    for index, column in enumerate(FEATURE_COLUMNS):
        frame[column] = [(row + index) % 7 for row in range(rows)]
    frame[TARGET_COLUMN] = [20 + row * 2 + (row % 3) for row in range(rows)]
    return frame


def test_xgboost_fits_predicts_and_uses_same_test_rows_as_baseline() -> None:
    frame = pd.concat([feature_series(), feature_series(station_id=2, fuel_type_id=2)], ignore_index=True)
    baseline = SevenDayMovingAverageBaseline().evaluate(frame)
    result = DemandXGBoostEvaluator().evaluate(frame)
    assert len(result.evaluation.predictions) == baseline.test_row_count
    assert result.evaluation.predictions.loc[:, ["date", "station_id", "fuel_type_id"]].equals(
        baseline.predictions.loc[:, ["date", "station_id", "fuel_type_id"]]
    )
    assert (result.evaluation.predictions.predicted_demand >= 0).all()
    assert set(result.artifact.feature_columns) == set(FEATURE_COLUMNS)
    assert len(result.artifact.models) == 2


def test_xgboost_is_deterministic_and_excludes_target_from_features() -> None:
    frame = feature_series()
    first = DemandXGBoostEvaluator().evaluate(frame)
    second = DemandXGBoostEvaluator().evaluate(frame)
    assert first.evaluation.mae == pytest.approx(second.evaluation.mae)
    assert first.evaluation.predictions.predicted_demand.tolist() == pytest.approx(
        second.evaluation.predictions.predicted_demand.tolist()
    )
    model = next(iter(first.artifact.models.values()))
    assert model.feature_names_in_.tolist() == list(FEATURE_COLUMNS)


def test_winner_activation_rule_never_promotes_equal_or_worse_xgboost() -> None:
    assert select_demand_winner(baseline_mae=10, xgboost_mae=9) == "xgboost"
    assert select_demand_winner(baseline_mae=10, xgboost_mae=10) == "baseline"
    assert select_demand_winner(baseline_mae=10, xgboost_mae=11) == "baseline"
