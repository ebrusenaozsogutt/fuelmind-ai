"""Unit coverage for calibrated 0–100 anomaly risk scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.anomaly_model import IsolationForestAnomalyModel, IsolationForestModelConfig
from app.ml.risk_scoring import AnomalyRiskLevel, AnomalyRiskScorer


def _decisions() -> np.ndarray:
    return np.array([-0.08, -0.04, -0.01, 0.01, 0.03, 0.05, 0.08, 0.12, 0.15, 0.18])


def _scorer() -> AnomalyRiskScorer:
    scorer = AnomalyRiskScorer()
    scorer.calibrate(_decisions())
    return scorer


def _features(rows: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "flow_rate": rng.normal(40, 1, rows),
        "pressure": rng.normal(3, 0.1, rows),
        "motor_current": rng.normal(10, 0.4, rows),
    })


def test_calibration_summary_and_monotonic_risk_direction() -> None:
    scorer = _scorer()
    risks = scorer.score_decision_values([0.15, 0.02, -0.05, -0.20])

    assert scorer.is_calibrated and scorer.calibration_summary is not None
    assert scorer.calibration_summary.calibration_row_count == 10
    assert risks.tolist() == sorted(risks.tolist())
    assert risks[0] <= 25 and risks[-1] >= 85


def test_uncalibrated_and_invalid_values_are_rejected() -> None:
    with pytest.raises(RuntimeError, match="calibrated"):
        AnomalyRiskScorer().score_decision_values([0.1])
    with pytest.raises(ValueError, match="at least"):
        AnomalyRiskScorer().calibrate([0.1, 0.2])
    for values in ([], [np.nan] * 8, [np.inf] * 8):
        with pytest.raises(ValueError):
            AnomalyRiskScorer().calibrate(values)


def test_risk_is_clamped_and_predict_is_not_forced_to_100() -> None:
    scorer = _scorer()
    risks = scorer.score_decision_values([-100, -0.01, 100])

    assert risks[0] == 100 and risks[-1] == 0
    assert 0 < risks[1] < 100

    class DiagnosticOutlierModel:
        def predict(self, _: pd.DataFrame) -> np.ndarray:
            return np.array([-1])

        def decision_function(self, _: pd.DataFrame) -> np.ndarray:
            return np.array([-0.01])

        def score_samples(self, _: pd.DataFrame) -> np.ndarray:
            return np.array([-0.51])

    result = scorer.score_features(DiagnosticOutlierModel(), pd.DataFrame({"x": [1]}))[0]  # type: ignore[arg-type]
    assert result.model_outlier is True and result.risk_score < 100


@pytest.mark.parametrize(
    ("score", "level"),
    [
        (0, AnomalyRiskLevel.NORMAL), (29, AnomalyRiskLevel.NORMAL),
        (30, AnomalyRiskLevel.WATCH), (49, AnomalyRiskLevel.WATCH),
        (50, AnomalyRiskLevel.MEDIUM), (69, AnomalyRiskLevel.MEDIUM),
        (70, AnomalyRiskLevel.HIGH), (84, AnomalyRiskLevel.HIGH),
        (85, AnomalyRiskLevel.CRITICAL), (100, AnomalyRiskLevel.CRITICAL),
    ],
)
def test_risk_level_boundaries(score: float, level: AnomalyRiskLevel) -> None:
    assert AnomalyRiskScorer.risk_level(score) is level


def test_batch_scoring_is_deterministic_and_preserves_input_order() -> None:
    scorer = _scorer()
    values = np.array([0.12, -0.03, 0.04, -0.08])

    first = scorer.score_decision_values(values)
    second = scorer.score_decision_values(values)

    assert np.array_equal(first, second)
    assert first[1] > first[2] > first[0]


def test_real_isolation_forest_outputs_produce_typed_risk_results() -> None:
    features = _features()
    model = IsolationForestAnomalyModel(IsolationForestModelConfig(n_estimators=100, random_state=7))
    model.fit(features)
    scorer = AnomalyRiskScorer()
    scorer.calibrate_model(model, features)
    normal = pd.DataFrame([[40, 3, 10]], columns=features.columns)
    outlier = pd.DataFrame([[3, 0.5, 25]], columns=features.columns)

    results = scorer.score_features(model, pd.concat([normal, outlier], ignore_index=True))

    assert len(results) == 2
    assert results[1].risk_score > results[0].risk_score
    assert results[1].model_outlier is True
    assert 85 <= results[1].risk_score <= 100
