"""Distribution-calibrated 0–100 anomaly risk scoring for Isolation Forest."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from app.ml.anomaly_model import IsolationForestAnomalyModel


class AnomalyRiskLevel(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class RiskScoringConfig:
    """Quantile anchors that map lower decision scores to higher risk."""

    quantiles: tuple[float, ...] = (0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99)
    risk_anchors: tuple[float, ...] = (100.0, 85.0, 60.0, 25.0, 10.0, 3.0, 0.0)
    minimum_calibration_rows: int = 8

    def __post_init__(self) -> None:
        if len(self.quantiles) != len(self.risk_anchors):
            raise ValueError("quantiles and risk_anchors must have the same length.")
        if tuple(sorted(self.quantiles)) != self.quantiles or not all(0 <= item <= 1 for item in self.quantiles):
            raise ValueError("quantiles must be sorted values between 0 and 1.")
        if tuple(sorted(self.risk_anchors, reverse=True)) != self.risk_anchors:
            raise ValueError("risk_anchors must be in descending risk order.")
        if self.minimum_calibration_rows < 2:
            raise ValueError("minimum_calibration_rows must be at least 2.")


@dataclass(frozen=True)
class RiskCalibrationSummary:
    calibration_row_count: int
    decision_min: float
    decision_q01: float
    decision_q05: float
    decision_q25: float
    decision_median: float
    decision_q75: float
    decision_q95: float
    decision_max: float
    quantile_decisions: tuple[float, ...]
    risk_anchors: tuple[float, ...]


@dataclass(frozen=True)
class AnomalyRiskResult:
    prediction: int
    decision_function: float
    score_samples: float
    risk_score: float
    risk_level: AnomalyRiskLevel
    model_outlier: bool


class AnomalyRiskScorer:
    """Convert trained-model decision values to a calibrated severity scale.

    The score is an anomaly-severity normalization, never a failure
    probability. Calibration learns only score-distribution anchors; it does
    not fit or modify the Isolation Forest itself.
    """

    def __init__(self, config: RiskScoringConfig | None = None) -> None:
        self.config = config or RiskScoringConfig()
        self._decision_anchors: np.ndarray | None = None
        self._calibration_summary: RiskCalibrationSummary | None = None

    @property
    def is_calibrated(self) -> bool:
        return self._decision_anchors is not None

    @property
    def calibration_summary(self) -> RiskCalibrationSummary | None:
        return self._calibration_summary

    def calibrate(self, training_decision_values: np.ndarray | pd.Series | list[float]) -> RiskCalibrationSummary:
        """Store deterministic decision-function quantiles from training data."""

        values = self._validate_values(training_decision_values, "training_decision_values")
        if len(values) < self.config.minimum_calibration_rows:
            raise ValueError(
                f"training_decision_values requires at least {self.config.minimum_calibration_rows} values."
            )
        anchors = np.quantile(values, self.config.quantiles)
        self._decision_anchors = anchors.astype(float)
        self._calibration_summary = RiskCalibrationSummary(
            calibration_row_count=len(values), decision_min=float(values.min()),
            decision_q01=float(np.quantile(values, 0.01)), decision_q05=float(np.quantile(values, 0.05)),
            decision_q25=float(np.quantile(values, 0.25)), decision_median=float(np.quantile(values, 0.50)),
            decision_q75=float(np.quantile(values, 0.75)), decision_q95=float(np.quantile(values, 0.95)),
            decision_max=float(values.max()), quantile_decisions=tuple(float(item) for item in anchors),
            risk_anchors=self.config.risk_anchors,
        )
        return self._calibration_summary

    def calibrate_model(self, model: IsolationForestAnomalyModel, training_features: pd.DataFrame) -> RiskCalibrationSummary:
        """Calibrate from the already-fitted model's training decision scores."""

        return self.calibrate(model.decision_function(training_features))

    def score_decision_values(self, decision_values: np.ndarray | pd.Series | list[float]) -> np.ndarray:
        """Map batch decision values to clipped 0–100 anomaly severity scores."""

        anchors = self._require_calibration()
        values = self._validate_values(decision_values, "decision_values")
        # np.interp is deterministic and monotonic. Anchor decisions ascend
        # from most anomalous to most normal, while risk anchors descend.
        unique_decisions, indices = np.unique(anchors, return_index=True)
        risks = np.asarray(self.config.risk_anchors, dtype=float)[indices]
        return np.clip(np.interp(values, unique_decisions, risks), 0.0, 100.0)

    def score_features(
        self, model: IsolationForestAnomalyModel, features: pd.DataFrame
    ) -> list[AnomalyRiskResult]:
        """Run model inference and return typed risk results for every row."""

        predictions = model.predict(features)
        decisions = model.decision_function(features)
        samples = model.score_samples(features)
        risks = self.score_decision_values(decisions)
        return [
            AnomalyRiskResult(
                prediction=int(prediction), decision_function=float(decision),
                score_samples=float(sample), risk_score=float(risk),
                risk_level=self.risk_level(float(risk)), model_outlier=bool(prediction == -1),
            )
            for prediction, decision, sample, risk in zip(predictions, decisions, samples, risks, strict=True)
        ]

    @staticmethod
    def risk_level(risk_score: float) -> AnomalyRiskLevel:
        if not 0 <= risk_score <= 100:
            raise ValueError("risk_score must be between 0 and 100.")
        if risk_score < 30:
            return AnomalyRiskLevel.NORMAL
        if risk_score < 50:
            return AnomalyRiskLevel.WATCH
        if risk_score < 70:
            return AnomalyRiskLevel.MEDIUM
        if risk_score < 85:
            return AnomalyRiskLevel.HIGH
        return AnomalyRiskLevel.CRITICAL

    def _require_calibration(self) -> np.ndarray:
        if self._decision_anchors is None:
            raise RuntimeError("AnomalyRiskScorer must be calibrated before scoring.")
        return self._decision_anchors

    @staticmethod
    def _validate_values(values: np.ndarray | pd.Series | list[float], name: str) -> np.ndarray:
        array = np.asarray(values, dtype=float)
        if array.ndim != 1 or array.size == 0:
            raise ValueError(f"{name} must be a non-empty one-dimensional sequence.")
        if not np.isfinite(array).all():
            raise ValueError(f"{name} must not contain NaN or infinity.")
        return array
