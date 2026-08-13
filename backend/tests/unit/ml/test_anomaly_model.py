"""Unit coverage for the Stage 8.3 Isolation Forest wrapper."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import NotFittedError

from app.ml.anomaly_model import IsolationForestAnomalyModel, IsolationForestModelConfig
from app.ml.feature_engineering import AnomalyFeatureEngineer


FEATURES = ("flow_rate", "pressure", "motor_current")


def _normal_features(rows: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "flow_rate": rng.normal(40, 1, rows),
        "pressure": rng.normal(3, 0.1, rows),
        "motor_current": rng.normal(10, 0.4, rows),
    })


def _model() -> IsolationForestAnomalyModel:
    return IsolationForestAnomalyModel(IsolationForestModelConfig(n_estimators=100, random_state=7))


def test_fit_summary_and_inference_outputs_follow_sklearn_semantics() -> None:
    features = _normal_features()
    model = _model()

    summary = model.fit(features)
    predictions = model.predict(features)
    decisions = model.decision_function(features)
    scores = model.score_samples(features)

    assert model.is_trained and model.feature_names == FEATURES
    assert summary.training_row_count == len(features) and summary.feature_count == 3
    assert summary.predicted_inlier_count_on_training + summary.predicted_outlier_count_on_training == len(features)
    assert len(predictions) == len(features) and set(predictions) <= {-1, 1}
    assert np.isfinite(decisions).all() and np.isfinite(scores).all()


def test_clear_synthetic_outlier_has_lower_anomaly_scores_than_normal_point() -> None:
    features = _normal_features()
    model = _model()
    model.fit(features)
    normal = pd.DataFrame([[40, 3, 10]], columns=FEATURES)
    outlier = pd.DataFrame([[3, 0.5, 25]], columns=FEATURES)

    assert model.decision_function(outlier)[0] < model.decision_function(normal)[0]
    assert model.score_samples(outlier)[0] < model.score_samples(normal)[0]
    assert model.predict(outlier)[0] == -1


def test_same_configuration_and_input_are_reproducible() -> None:
    features = _normal_features()
    first, second = _model(), _model()
    first.fit(features)
    second.fit(features)

    assert np.allclose(first.decision_function(features), second.decision_function(features))
    assert np.array_equal(first.predict(features), second.predict(features))


def test_inference_reorders_named_columns_and_ignores_metadata() -> None:
    features = _normal_features(10)
    model = _model()
    model.fit(features)
    shuffled = features.loc[:, ["motor_current", "flow_rate", "pressure"]].assign(station_id=1)

    assert np.allclose(model.decision_function(features), model.decision_function(shuffled))


@pytest.mark.parametrize(
    "features, message",
    [
        (pd.DataFrame(), "at least one"),
        (pd.DataFrame(index=[0]), "at least one"),
        (pd.DataFrame({"flow_rate": [np.nan]}), "NaN or infinity"),
        (pd.DataFrame({"flow_rate": [np.inf]}), "NaN or infinity"),
        (pd.DataFrame({"flow_rate": ["not-a-number"]}), "numeric"),
    ],
)
def test_fit_rejects_invalid_feature_matrices(features: pd.DataFrame, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _model().fit(features)


def test_fit_rejects_duplicate_columns_and_untrained_inference_is_clear() -> None:
    duplicate = pd.DataFrame(np.ones((2, 2)), columns=["flow_rate", "flow_rate"])
    with pytest.raises(ValueError, match="duplicate"):
        _model().fit(duplicate)
    with pytest.raises(NotFittedError, match="must be fitted"):
        _model().predict(_normal_features(1))


def test_missing_required_inference_feature_is_rejected() -> None:
    model = _model()
    model.fit(_normal_features())
    with pytest.raises(ValueError, match="missing required"):
        model.predict(pd.DataFrame({"flow_rate": [40], "pressure": [3]}))


def test_feature_engineering_output_can_be_fitted_as_the_pipeline_contract() -> None:
    timestamps = pd.date_range("2026-01-01", periods=10, freq="5min", tz="UTC")
    raw = pd.DataFrame({
        "reading_timestamp": timestamps, "station_id": 1, "pump_id": 1, "tank_id": 1,
        "simulation_run_id": 1, "sequence_number": range(10), "source_type": "SIMULATION",
        "flow_rate": range(30, 40), "pressure": range(2, 12), "motor_current": range(8, 18),
        "pump_temperature": range(20, 30), "error_count": range(10),
        "working_duration": np.arange(10) / 12, "data_quality_score": 95,
        "tank_level": np.nan, "true_tank_level": np.nan, "temperature": np.nan, "water_level": np.nan,
    })
    matrix = AnomalyFeatureEngineer().engineer(raw).features["pump"]
    model = _model()

    summary = model.fit(matrix)

    assert summary.feature_names == tuple(matrix.columns)
    assert len(model.predict(matrix)) == len(matrix)
