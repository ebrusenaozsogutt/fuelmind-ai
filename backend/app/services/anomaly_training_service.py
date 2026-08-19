"""Orchestration of the real Stage 8 anomaly-training pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.ml.anomaly_model import IsolationForestAnomalyModel
from app.ml.explainability import AnomalyExplanationService
from app.ml.feature_engineering import AnomalyFeatureEngineer
from app.ml.model_registry import AnomalyModelRegistry, ModelFamily, RegistrySaveResult
from app.ml.preprocessing import AnomalyTrainingDatasetBuilder
from app.ml.risk_scoring import AnomalyRiskScorer
from app.repositories.station_repository import StationRepository
from app.schemas.model_registry import AnomalyModelTrainRequest


@dataclass(frozen=True)
class AnomalyTrainingResult:
    registry_result: RegistrySaveResult
    diagnostics: dict[str, object]


class AnomalyTrainingService:
    """Build data, engineer features, fit, calibrate, explain, and register."""

    def __init__(
        self,
        db: Session,
        *,
        registry_root: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        self.db = db
        self.registry = AnomalyModelRegistry(
            db, registry_root=registry_root, project_root=project_root
        )

    def train(self, request: AnomalyModelTrainRequest) -> AnomalyTrainingResult:
        station = StationRepository(self.db).get(request.station_id)
        if station is None:
            raise NotFoundError("Station not found.")
        if not station.is_active:
            raise BusinessRuleError("Cannot train a model for an inactive station.")

        dataset = AnomalyTrainingDatasetBuilder(self.db).build(
            station_id=request.station_id,
            start_time=request.start_time,
            end_time=request.end_time,
            source_types=request.source_types,
        )
        engineered = AnomalyFeatureEngineer().engineer(dataset)
        family: ModelFamily = request.model_family
        features = engineered.features[family]
        metadata = engineered.metadata[family]
        if features.empty:
            raise BusinessRuleError(
                f"No model-ready {family} rows remain after preprocessing and feature engineering."
            )
        if len(features) < 8:
            raise BusinessRuleError(
                f"At least 8 model-ready {family} rows are required for risk calibration."
            )

        model = IsolationForestAnomalyModel()
        training_summary = model.fit(features)
        scorer = AnomalyRiskScorer()
        calibration = scorer.calibrate_model(model, features)
        reference_profile = AnomalyExplanationService().fit_reference(
            features, family=family
        )
        timestamps = metadata["reading_timestamp"]
        registry_result = self.registry.save(
            model=model,
            risk_scorer=scorer,
            model_family=family,
            reference_profile=reference_profile,
            training_start_date=timestamps.min().date(),
            training_end_date=timestamps.max().date(),
            extra_metadata={
                "training_station_id": request.station_id,
                # Keep the complete selection trace beside the immutable model
                # version so a registry row can be audited without rerunning a
                # query against subsequently changed operational data.
                "training_data_summary": {
                    "dataset": asdict(dataset.summary),
                    "feature_engineering": asdict(engineered.summary),
                    "model_family": family,
                    "source_types": [source.value for source in request.source_types]
                    if request.source_types is not None else None,
                },
            },
        )
        return AnomalyTrainingResult(
            registry_result=registry_result,
            diagnostics={
                "dataset": asdict(dataset.summary),
                "feature_engineering": asdict(engineered.summary),
                "model": asdict(training_summary),
                "risk_calibration": asdict(calibration),
            },
        )
