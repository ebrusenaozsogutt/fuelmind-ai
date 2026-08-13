"""Isolation Forest wrapper with a stable, validated feature contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.exceptions import NotFittedError

from app.utils.datetime_utils import utc_now


@dataclass(frozen=True)
class IsolationForestModelConfig:
    """Reproducible, conservative configuration for the first anomaly model."""

    n_estimators: int = 200
    contamination: Literal["auto"] | float = "auto"
    max_samples: Literal["auto"] | int | float = "auto"
    random_state: int = 42
    n_jobs: int | None = None

    def __post_init__(self) -> None:
        if self.n_estimators <= 0:
            raise ValueError("n_estimators must be positive.")
        if isinstance(self.contamination, float) and not 0 < self.contamination <= 0.5:
            raise ValueError("contamination must be 'auto' or a value in (0, 0.5].")


@dataclass(frozen=True)
class AnomalyModelTrainingSummary:
    """Diagnostic facts from fitting an unsupervised anomaly model."""

    training_row_count: int
    feature_count: int
    feature_names: tuple[str, ...]
    trained_at: datetime
    n_estimators: int
    contamination: str | float
    max_samples: str | int | float
    random_state: int
    predicted_inlier_count_on_training: int
    predicted_outlier_count_on_training: int
    outlier_fraction_on_training: float
    decision_function_min: float
    decision_function_max: float
    decision_function_mean: float
    score_samples_min: float
    score_samples_max: float
    score_samples_mean: float


class IsolationForestAnomalyModel:
    """Fit and query Isolation Forest without producing FuelMind risk scores.

    DataFrame column names are deliberately required at every boundary. This
    avoids the silent feature-order mistakes that raw NumPy arrays can cause.
    """

    def __init__(self, config: IsolationForestModelConfig | None = None) -> None:
        self.config = config or IsolationForestModelConfig()
        self._model: IsolationForest | None = None
        self._feature_names: tuple[str, ...] = ()
        self._training_summary: AnomalyModelTrainingSummary | None = None

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self._feature_names

    @property
    def training_summary(self) -> AnomalyModelTrainingSummary | None:
        return self._training_summary

    def fit(self, features: pd.DataFrame) -> AnomalyModelTrainingSummary:
        """Fit a real Isolation Forest and retain its ordered feature contract."""

        matrix, feature_names = self._validate_training_features(features)
        model = IsolationForest(
            n_estimators=self.config.n_estimators,
            contamination=self.config.contamination,
            max_samples=self.config.max_samples,
            random_state=self.config.random_state,
            n_jobs=self.config.n_jobs,
        )
        model.fit(matrix)
        predictions = model.predict(matrix)
        decisions = model.decision_function(matrix)
        scores = model.score_samples(matrix)
        self._model = model
        self._feature_names = feature_names
        self._training_summary = self._summary(predictions, decisions, scores, feature_names)
        return self._training_summary

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Return scikit-learn semantics: +1 for inlier and -1 for outlier."""

        return self._require_model().predict(self._prepare_inference(features))

    def decision_function(self, features: pd.DataFrame) -> np.ndarray:
        """Return relative normality scores; lower values are more anomalous."""

        return self._require_model().decision_function(self._prepare_inference(features))

    def score_samples(self, features: pd.DataFrame) -> np.ndarray:
        """Return raw Isolation Forest scores; lower values are more anomalous."""

        return self._require_model().score_samples(self._prepare_inference(features))

    def _require_model(self) -> IsolationForest:
        if self._model is None:
            raise NotFittedError("IsolationForestAnomalyModel must be fitted before inference.")
        return self._model

    @staticmethod
    def _validate_training_features(features: pd.DataFrame) -> tuple[np.ndarray, tuple[str, ...]]:
        if not isinstance(features, pd.DataFrame):
            raise TypeError("features must be a pandas DataFrame with named columns.")
        if features.shape[1] == 0:
            raise ValueError("features must contain at least one model feature.")
        if features.empty:
            raise ValueError("features cannot be empty.")
        if features.columns.has_duplicates:
            raise ValueError("features cannot contain duplicate feature names.")
        names = tuple(str(column) for column in features.columns)
        try:
            matrix = features.astype(float).to_numpy()
        except (TypeError, ValueError) as exc:
            raise ValueError("model features must be numeric.") from exc
        if not np.isfinite(matrix).all():
            raise ValueError("model features must not contain NaN or infinity.")
        return matrix, names

    def _prepare_inference(self, features: pd.DataFrame) -> np.ndarray:
        self._require_model()
        if not isinstance(features, pd.DataFrame):
            raise TypeError("features must be a pandas DataFrame with named columns.")
        if features.columns.has_duplicates:
            raise ValueError("features cannot contain duplicate feature names.")
        missing = [name for name in self._feature_names if name not in features.columns]
        if missing:
            raise ValueError(f"inference features are missing required columns: {', '.join(missing)}.")
        # Metadata or future non-model columns are intentionally ignored. The
        # stored contract controls both the selected names and their order.
        ordered = features.loc[:, list(self._feature_names)]
        _, _ = self._validate_training_features(ordered)
        return ordered.astype(float).to_numpy()

    def _summary(
        self,
        predictions: np.ndarray,
        decisions: np.ndarray,
        scores: np.ndarray,
        feature_names: tuple[str, ...],
    ) -> AnomalyModelTrainingSummary:
        inliers = int((predictions == 1).sum())
        outliers = int((predictions == -1).sum())
        return AnomalyModelTrainingSummary(
            training_row_count=len(predictions), feature_count=len(feature_names),
            feature_names=feature_names, trained_at=utc_now(),
            n_estimators=self.config.n_estimators, contamination=self.config.contamination,
            max_samples=self.config.max_samples, random_state=self.config.random_state,
            predicted_inlier_count_on_training=inliers, predicted_outlier_count_on_training=outliers,
            outlier_fraction_on_training=outliers / len(predictions),
            decision_function_min=float(decisions.min()), decision_function_max=float(decisions.max()),
            decision_function_mean=float(decisions.mean()), score_samples_min=float(scores.min()),
            score_samples_max=float(scores.max()), score_samples_mean=float(scores.mean()),
        )
