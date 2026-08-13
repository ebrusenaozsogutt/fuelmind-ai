"""Trusted local artifact storage and database-backed anomaly model registry."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from threading import RLock
from typing import Literal

import joblib
from sklearn.exceptions import NotFittedError
from sklearn.utils.validation import check_is_fitted
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessRuleError, NotFoundError
from app.ml.anomaly_model import (
    AnomalyModelTrainingSummary,
    IsolationForestAnomalyModel,
    IsolationForestModelConfig,
)
from app.ml.explainability import FeatureReferenceProfile
from app.ml.risk_scoring import AnomalyRiskScorer, RiskCalibrationSummary
from app.models.model_version import ModelVersion
from app.repositories.model_version_repository import ModelVersionRepository
from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)

ARTIFACT_SCHEMA_VERSION = 1
ANOMALY_MODEL_TYPE = "isolation_forest"
ModelFamily = Literal["pump", "tank"]


class ModelArtifactNotFoundError(NotFoundError):
    """Raised when registry metadata points to a missing trusted artifact."""


class ModelArtifactInvalidError(BusinessRuleError):
    """Raised when an artifact fails integrity or contract validation."""


class ModelVersionNotFoundError(NotFoundError):
    """Raised when the requested registry row does not exist."""


class NoActiveModelError(NotFoundError):
    """Raised when a model family has no active registry version."""


@dataclass(frozen=True)
class AnomalyModelArtifact:
    """Complete, versioned inference contract serialized as one trusted unit."""

    artifact_version: int
    registry_version: str
    model_type: str
    model_family: ModelFamily
    model: IsolationForestAnomalyModel
    feature_names: tuple[str, ...]
    model_config: IsolationForestModelConfig
    training_summary: AnomalyModelTrainingSummary
    risk_scorer: AnomalyRiskScorer
    risk_calibration: RiskCalibrationSummary
    reference_profile: FeatureReferenceProfile
    created_at: datetime


@dataclass(frozen=True)
class RegistrySaveResult:
    """The persisted DB row and validated artifact produced by a save."""

    model_version: ModelVersion
    artifact: AnomalyModelArtifact


_artifact_cache: dict[tuple[int, str], AnomalyModelArtifact] = {}
_cache_lock = RLock()


class AnomalyModelRegistry:
    """Persist, validate, activate, and cache Isolation Forest artifacts."""

    def __init__(
        self,
        db: Session,
        *,
        registry_root: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        self.db = db
        self.repository = ModelVersionRepository(db)
        self.registry_root = (registry_root or settings.MODEL_REGISTRY_ROOT).resolve()
        self.project_root = (
            project_root or self.registry_root.parent
        ).resolve()
        if not self.registry_root.is_relative_to(self.project_root):
            raise ValueError("registry_root must be inside project_root.")

    def save(
        self,
        *,
        model: IsolationForestAnomalyModel,
        risk_scorer: AnomalyRiskScorer,
        model_family: ModelFamily,
        reference_profile: FeatureReferenceProfile,
        training_start_date: date,
        training_end_date: date,
        activate: bool | None = None,
        extra_metadata: dict[str, object] | None = None,
    ) -> RegistrySaveResult:
        """Atomically materialize an artifact and its registry index row."""

        self._validate_family(model_family)
        self._validate_save_contract(model, risk_scorer, reference_profile, model_family)
        if training_start_date > training_end_date:
            raise ValueError("training_start_date cannot be after training_end_date.")
        summary = model.training_summary
        calibration = risk_scorer.calibration_summary
        assert summary is not None and calibration is not None

        version = self.repository.next_version(ANOMALY_MODEL_TYPE)
        artifact = AnomalyModelArtifact(
            artifact_version=ARTIFACT_SCHEMA_VERSION,
            registry_version=version,
            model_type=ANOMALY_MODEL_TYPE,
            model_family=model_family,
            model=model,
            feature_names=model.feature_names,
            model_config=model.config,
            training_summary=summary,
            risk_scorer=risk_scorer,
            risk_calibration=calibration,
            reference_profile=reference_profile,
            created_at=utc_now(),
        )
        family_dir = self.registry_root / "anomaly"
        family_dir.mkdir(parents=True, exist_ok=True)
        final_path = family_dir / f"isolation_forest_{model_family}_{version}.joblib"
        relative_path = final_path.relative_to(self.project_root).as_posix()
        temp_path: Path | None = None
        finalized = False
        try:
            handle, raw_temp_path = tempfile.mkstemp(
                prefix=f".{final_path.stem}-", suffix=".tmp", dir=family_dir
            )
            os.close(handle)
            temp_path = Path(raw_temp_path)
            joblib.dump(artifact, temp_path)
            loaded = self._load_joblib(temp_path)
            self._validate_artifact(loaded)
            digest = self._sha256(temp_path)
            size = temp_path.stat().st_size
            current_active = self.repository.get_active(
                ANOMALY_MODEL_TYPE, model_family
            )
            should_activate = activate is True or (
                activate is None and current_active is None
            )
            if should_activate and current_active is not None:
                current_active.is_active = False
                self.db.flush()
            record = self.repository.create(
                {
                    "model_type": ANOMALY_MODEL_TYPE,
                    "model_family": model_family,
                    "version": version,
                    "file_path": relative_path,
                    "artifact_sha256": digest,
                    "artifact_size_bytes": size,
                    "metadata_json": {
                        **self._metadata(artifact),
                        **(extra_metadata or {}),
                    },
                    "training_start_date": training_start_date,
                    "training_end_date": training_end_date,
                    "training_row_count": summary.training_row_count,
                    "mae": None,
                    "rmse": None,
                    "mape": None,
                    "is_active": should_activate,
                    "trained_at": summary.trained_at,
                }
            )
            os.replace(temp_path, final_path)
            finalized = True
            self.db.commit()
        except Exception:
            self.db.rollback()
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            if finalized:
                final_path.unlink(missing_ok=True)
            raise
        self.invalidate_cache()
        logger.info(
            "Saved anomaly model artifact path=%s size=%d version=%s rows=%d features=%d",
            relative_path,
            size,
            version,
            summary.training_row_count,
            summary.feature_count,
        )
        return RegistrySaveResult(record, artifact)

    def list_versions(
        self,
        *,
        model_family: ModelFamily | None = None,
    ) -> list[ModelVersion]:
        if model_family is not None:
            self._validate_family(model_family)
        return self.repository.list(
            model_type=ANOMALY_MODEL_TYPE, model_family=model_family
        )

    def get_version(self, version_id: int) -> ModelVersion:
        record = self.repository.get(version_id)
        if record is None or record.model_type != ANOMALY_MODEL_TYPE:
            raise ModelVersionNotFoundError("Anomaly model version not found.")
        return record

    def load_version(self, version_id: int) -> AnomalyModelArtifact:
        return self._load_record(self.get_version(version_id))

    def get_active(self, model_family: ModelFamily) -> AnomalyModelArtifact:
        self._validate_family(model_family)
        record = self.repository.get_active(ANOMALY_MODEL_TYPE, model_family)
        if record is None:
            raise NoActiveModelError(
                f"No active anomaly model exists for family '{model_family}'."
            )
        return self._load_record(record)

    def activate(self, version_id: int) -> ModelVersion:
        record = self.get_version(version_id)
        self._validate_family(record.model_family)
        self._load_record(record)
        try:
            self.repository.activate(record)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.invalidate_cache()
        return record

    def artifact_available(self, record: ModelVersion) -> bool:
        try:
            path = self._artifact_path(record)
        except ModelArtifactInvalidError:
            return False
        return path.is_file()

    @staticmethod
    def invalidate_cache() -> None:
        with _cache_lock:
            _artifact_cache.clear()

    def _load_record(self, record: ModelVersion) -> AnomalyModelArtifact:
        path = self._artifact_path(record)
        if not path.is_file():
            raise ModelArtifactNotFoundError(
                f"Artifact for model version {record.version} was not found."
            )
        digest = self._sha256(path)
        if digest != record.artifact_sha256:
            raise ModelArtifactInvalidError(
                f"Artifact integrity check failed for model version {record.version}."
            )
        cache_key = (record.id, digest)
        with _cache_lock:
            cached = _artifact_cache.get(cache_key)
        if cached is not None:
            return cached
        artifact = self._load_joblib(path)
        self._validate_artifact(artifact)
        if (
            artifact.registry_version != record.version
            or artifact.model_type != record.model_type
            or artifact.model_family != record.model_family
        ):
            raise ModelArtifactInvalidError(
                "Artifact identity does not match its model_versions record."
            )
        with _cache_lock:
            _artifact_cache[cache_key] = artifact
        return artifact

    def _artifact_path(self, record: ModelVersion) -> Path:
        candidate = (self.project_root / Path(record.file_path)).resolve()
        if not candidate.is_relative_to(self.registry_root):
            raise ModelArtifactInvalidError(
                "Registry record points outside the trusted model directory."
            )
        return candidate

    @staticmethod
    def _load_joblib(path: Path) -> AnomalyModelArtifact:
        try:
            return joblib.load(path)
        except Exception as exc:
            raise ModelArtifactInvalidError(
                "Model artifact could not be deserialized."
            ) from exc

    @staticmethod
    def _validate_artifact(artifact: object) -> None:
        if not isinstance(artifact, AnomalyModelArtifact):
            raise ModelArtifactInvalidError("Unexpected model artifact type.")
        if artifact.artifact_version != ARTIFACT_SCHEMA_VERSION:
            raise ModelArtifactInvalidError("Unsupported model artifact schema version.")
        if artifact.model_type != ANOMALY_MODEL_TYPE:
            raise ModelArtifactInvalidError("Unexpected artifact model type.")
        if artifact.model_family not in {"pump", "tank"}:
            raise ModelArtifactInvalidError("Unexpected artifact model family.")
        if not artifact.feature_names or artifact.feature_names != artifact.model.feature_names:
            raise ModelArtifactInvalidError("Artifact feature contract is invalid.")
        if not artifact.model.is_trained or artifact.model.training_summary is None:
            raise ModelArtifactInvalidError("Artifact model is not trained.")
        if artifact.model.training_summary.feature_names != artifact.feature_names:
            raise ModelArtifactInvalidError("Artifact training feature contract is invalid.")
        if artifact.model_config != artifact.model.config:
            raise ModelArtifactInvalidError("Artifact model configuration is inconsistent.")
        if not artifact.risk_scorer.is_calibrated or artifact.risk_calibration is None:
            raise ModelArtifactInvalidError("Artifact risk calibration is missing.")
        if artifact.risk_scorer.calibration_summary != artifact.risk_calibration:
            raise ModelArtifactInvalidError("Artifact risk calibration is inconsistent.")
        if artifact.reference_profile.family != artifact.model_family:
            raise ModelArtifactInvalidError("Artifact reference profile family is invalid.")
        if artifact.reference_profile.feature_names != artifact.feature_names:
            raise ModelArtifactInvalidError("Artifact reference feature contract is invalid.")
        try:
            check_is_fitted(artifact.model._require_model())
        except (NotFittedError, TypeError) as exc:
            raise ModelArtifactInvalidError("Artifact estimator is not fitted.") from exc

    @staticmethod
    def _validate_family(model_family: str) -> None:
        if model_family not in {"pump", "tank"}:
            raise ValueError("model_family must be 'pump' or 'tank'.")

    @staticmethod
    def _validate_save_contract(
        model: IsolationForestAnomalyModel,
        risk_scorer: AnomalyRiskScorer,
        reference_profile: FeatureReferenceProfile,
        model_family: str,
    ) -> None:
        if not model.is_trained or model.training_summary is None:
            raise ValueError("A trained anomaly model is required.")
        if not risk_scorer.is_calibrated or risk_scorer.calibration_summary is None:
            raise ValueError("A calibrated anomaly risk scorer is required.")
        if reference_profile.family != model_family:
            raise ValueError("Reference profile family must match model_family.")
        if reference_profile.feature_names != model.feature_names:
            raise ValueError("Reference profile must match the model feature contract.")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _metadata(artifact: AnomalyModelArtifact) -> dict[str, object]:
        training_summary = asdict(artifact.training_summary)
        training_summary["trained_at"] = artifact.training_summary.trained_at.isoformat()
        return {
            "artifact_schema_version": artifact.artifact_version,
            "feature_count": len(artifact.feature_names),
            "feature_names": list(artifact.feature_names),
            "model_config": asdict(artifact.model_config),
            "risk_calibration": asdict(artifact.risk_calibration),
            "training_summary": training_summary,
            "reference_profile_in_artifact": True,
        }
