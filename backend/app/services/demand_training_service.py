"""Train, compare, persist, and conditionally activate the demand XGBoost model."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from sqlalchemy.orm import Session

from app.ml.demand_model import DemandModelEvaluation, SevenDayMovingAverageBaseline
from app.ml.demand_preprocessing import DemandForecastDatasetBuilder
from app.ml.demand_xgboost import DemandXGBoostArtifact, DemandXGBoostEvaluator, XGBoostEvaluationResult
from app.models.model_version import ModelVersion
from app.repositories.model_version_repository import ModelVersionRepository
from app.config import settings

DEMAND_MODEL_FAMILY = "demand"


def select_demand_winner(*, baseline_mae: float, xgboost_mae: float) -> str:
    """MAE is the sole activation decision; ties intentionally retain baseline."""

    return "xgboost" if xgboost_mae < baseline_mae else "baseline"


@dataclass(frozen=True)
class DemandTrainingResult:
    dataset_summary: object
    baseline: DemandModelEvaluation
    xgboost: DemandModelEvaluation
    winner: str
    registry_record: ModelVersion
    feature_importance: tuple[tuple[str, float], ...]


class DemandTrainingService:
    """Service layer; no production future forecast is generated here."""

    def __init__(self, db: Session, *, registry_root: Path | None = None) -> None:
        self.db = db
        self.registry_root = (registry_root or settings.MODEL_REGISTRY_ROOT).resolve()
        self.repository = ModelVersionRepository(db)

    def train(self, *, station_id: int | None = None, start_at: date | None = None, end_at: date | None = None) -> DemandTrainingResult:
        dataset = DemandForecastDatasetBuilder(self.db).build(
            station_id=station_id, start_at=start_at, end_at=end_at
        )
        baseline = SevenDayMovingAverageBaseline().evaluate(dataset.feature_dataframe)
        xgboost_result: XGBoostEvaluationResult = DemandXGBoostEvaluator().evaluate(dataset.feature_dataframe)
        winner = select_demand_winner(
            baseline_mae=baseline.mae, xgboost_mae=xgboost_result.evaluation.mae
        )
        record = self._save(xgboost_result.artifact, xgboost_result, baseline, winner == "xgboost")
        return DemandTrainingResult(
            dataset_summary=dataset.summary, baseline=baseline, xgboost=xgboost_result.evaluation,
            winner=winner, registry_record=record, feature_importance=xgboost_result.feature_importance,
        )

    def _save(self, artifact: DemandXGBoostArtifact, result: XGBoostEvaluationResult, baseline: DemandModelEvaluation, activate: bool) -> ModelVersion:
        version = self.repository.next_version(artifact.model_type)
        directory = self.registry_root / "demand"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"demand_xgboost_{version}.joblib"
        joblib.dump(artifact, path)
        digest = self._sha256(path)
        metadata = {
            "feature_count": len(artifact.feature_columns), "feature_names": list(artifact.feature_columns),
            "target_column": artifact.target_column, "series_scope": sorted(artifact.models),
            "model_config": artifact.config, "feature_importance": list(result.feature_importance),
            "residual_abs_p90": float(np.quantile(result.evaluation.predictions["absolute_error"], .90)),
            "winner": "xgboost" if activate else "baseline",
            "baseline_metrics": {"mae": baseline.mae, "rmse": baseline.rmse, "mape": baseline.mape,
                "training_row_count": baseline.train_row_count,
                "residual_abs_p90": float(np.quantile(baseline.predictions["absolute_error"], .90))},
        }
        try:
            record = self.repository.create({
                "model_type": artifact.model_type, "model_family": DEMAND_MODEL_FAMILY, "version": version,
                "file_path": path.relative_to(self.registry_root.parent).as_posix(),
                "artifact_sha256": digest, "artifact_size_bytes": path.stat().st_size, "metadata_json": metadata,
                "training_start_date": min(item.predictions.date.min() for item in result.evaluation.series_evaluations),
                "training_end_date": max(item.predictions.date.max() for item in result.evaluation.series_evaluations),
                "training_row_count": artifact.training_row_count, "mae": result.evaluation.mae,
                "rmse": result.evaluation.rmse, "mape": result.evaluation.mape, "is_active": False,
            })
            if activate:
                self.repository.activate(record)
            self.db.commit()
            return record
        except Exception:
            self.db.rollback()
            path.unlink(missing_ok=True)
            raise

    @staticmethod
    def load_artifact(path: Path) -> DemandXGBoostArtifact:
        artifact = joblib.load(path)
        if not isinstance(artifact, DemandXGBoostArtifact):
            raise ValueError("Unexpected demand model artifact.")
        return artifact

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
