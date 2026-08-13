"""Unit and lifecycle coverage for the Stage 8.7 model registry."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.ml.anomaly_model import IsolationForestAnomalyModel, IsolationForestModelConfig
from app.ml.explainability import AnomalyExplanationService
from app.ml.model_registry import (
    AnomalyModelRegistry,
    ModelArtifactInvalidError,
    ModelArtifactNotFoundError,
)
from app.ml.risk_scoring import AnomalyRiskScorer
from app.models.model_version import ModelVersion


@pytest.fixture
def registry_context(tmp_path: Path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[ModelVersion.__table__])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    project_root = tmp_path / "project"
    registry_root = project_root / "trained_models"
    registry = AnomalyModelRegistry(
        session, registry_root=registry_root, project_root=project_root
    )
    try:
        yield session, registry, project_root
    finally:
        AnomalyModelRegistry.invalidate_cache()
        session.close()
        engine.dispose()


def _contract(*, seed: int = 42, family: str = "pump"):
    random = np.random.default_rng(seed)
    features = pd.DataFrame(
        random.normal(size=(48, 4)),
        columns=["flow_rate", "pressure", "motor_current", "temperature"],
    )
    config = IsolationForestModelConfig(n_estimators=32, random_state=seed)
    model = IsolationForestAnomalyModel(config)
    model.fit(features)
    scorer = AnomalyRiskScorer()
    scorer.calibrate_model(model, features)
    profile = AnomalyExplanationService().fit_reference(features, family=family)
    return features, model, scorer, profile


def _save(registry: AnomalyModelRegistry, *, seed: int = 42):
    features, model, scorer, profile = _contract(seed=seed)
    result = registry.save(
        model=model,
        risk_scorer=scorer,
        model_family="pump",
        reference_profile=profile,
        training_start_date=date(2026, 8, 1),
        training_end_date=date(2026, 8, 10),
    )
    return features, result


def test_save_creates_artifact_db_record_and_portable_metadata(registry_context) -> None:
    session, registry, project_root = registry_context
    _, result = _save(registry)
    record = result.model_version

    assert record.id is not None
    assert session.get(ModelVersion, record.id) is record
    assert record.version == "v0001"
    assert record.is_active is True
    assert record.mae is record.rmse is record.mape is None
    assert not Path(record.file_path).is_absolute()
    artifact_path = project_root / record.file_path
    assert artifact_path.is_file()
    assert artifact_path.stat().st_size == record.artifact_size_bytes
    assert record.metadata_json["feature_names"] == list(result.artifact.feature_names)
    assert record.metadata_json["training_summary"]["outlier_fraction_on_training"] == (
        result.artifact.training_summary.outlier_fraction_on_training
    )


def test_reload_preserves_model_calibration_config_summary_and_contract(registry_context) -> None:
    session, registry, project_root = registry_context
    features, result = _save(registry)
    before_decisions = result.artifact.model.decision_function(features.iloc[:4])
    before_risk = result.artifact.risk_scorer.score_features(
        result.artifact.model, features.iloc[:4]
    )

    restarted = AnomalyModelRegistry(
        session,
        registry_root=project_root / "trained_models",
        project_root=project_root,
    )
    AnomalyModelRegistry.invalidate_cache()
    loaded = restarted.get_active("pump")

    np.testing.assert_allclose(
        loaded.model.decision_function(features.iloc[:4]), before_decisions
    )
    np.testing.assert_array_equal(
        loaded.model.predict(features.iloc[:4]),
        result.artifact.model.predict(features.iloc[:4]),
    )
    assert [item.risk_score for item in loaded.risk_scorer.score_features(loaded.model, features.iloc[:4])] == pytest.approx(
        [item.risk_score for item in before_risk]
    )
    assert loaded.feature_names == tuple(features.columns)
    assert loaded.model_config == result.artifact.model_config
    assert loaded.training_summary == result.artifact.training_summary
    assert loaded.risk_calibration == result.artifact.risk_calibration
    assert loaded.reference_profile == result.artifact.reference_profile


def test_versions_increment_and_second_model_does_not_replace_active(registry_context) -> None:
    _, registry, _ = registry_context
    _, first = _save(registry, seed=1)
    _, second = _save(registry, seed=2)

    assert (first.model_version.version, second.model_version.version) == (
        "v0001",
        "v0002",
    )
    assert first.model_version.is_active is True
    assert second.model_version.is_active is False
    assert registry.get_active("pump").registry_version == "v0001"


def test_activate_switches_single_active_version_and_invalidates_cache(registry_context) -> None:
    session, registry, _ = registry_context
    _, first = _save(registry, seed=1)
    _, second = _save(registry, seed=2)
    cached = registry.get_active("pump")
    assert registry.get_active("pump") is cached

    activated = registry.activate(second.model_version.id)
    session.refresh(first.model_version)

    assert activated.is_active is True
    assert first.model_version.is_active is False
    assert len([item for item in registry.list_versions() if item.is_active]) == 1
    loaded = registry.get_active("pump")
    assert loaded.registry_version == "v0002"
    assert loaded is not cached


def test_missing_or_corrupt_artifacts_raise_clear_errors(registry_context) -> None:
    _, registry, project_root = registry_context
    _, result = _save(registry)
    path = project_root / result.model_version.file_path
    path.unlink()
    with pytest.raises(ModelArtifactNotFoundError, match="was not found"):
        registry.load_version(result.model_version.id)

    path.write_bytes(b"not a joblib artifact")
    with pytest.raises(ModelArtifactInvalidError, match="integrity check"):
        registry.load_version(result.model_version.id)


def test_wrong_artifact_type_is_rejected_after_integrity_check(registry_context) -> None:
    _, registry, project_root = registry_context
    _, result = _save(registry)
    path = project_root / result.model_version.file_path
    joblib.dump({"unexpected": "payload"}, path)
    result.model_version.artifact_sha256 = registry._sha256(path)
    registry.db.commit()
    AnomalyModelRegistry.invalidate_cache()

    with pytest.raises(ModelArtifactInvalidError, match="Unexpected model artifact type"):
        registry.load_version(result.model_version.id)


def test_registry_rejects_path_traversal_and_missing_activation_artifact(registry_context) -> None:
    _, registry, project_root = registry_context
    _, first = _save(registry, seed=1)
    _, second = _save(registry, seed=2)
    first.model_version.file_path = "../outside.joblib"
    registry.db.commit()
    with pytest.raises(ModelArtifactInvalidError, match="outside"):
        registry.load_version(first.model_version.id)

    second_path = project_root / second.model_version.file_path
    second_path.unlink()
    with pytest.raises(ModelArtifactNotFoundError):
        registry.activate(second.model_version.id)
    assert second.model_version.is_active is False


def test_first_version_of_each_family_can_be_active(registry_context) -> None:
    _, registry, _ = registry_context
    _, pump = _save(registry)
    _, model, scorer, profile = _contract(seed=9, family="tank")
    tank = registry.save(
        model=model,
        risk_scorer=scorer,
        model_family="tank",
        reference_profile=profile,
        training_start_date=date(2026, 8, 1),
        training_end_date=date(2026, 8, 10),
    )

    assert pump.model_version.is_active is True
    assert tank.model_version.is_active is True
    assert registry.get_active("pump").model_family == "pump"
    assert registry.get_active("tank").model_family == "tank"


def test_commit_failure_rolls_back_db_and_removes_final_artifact(
    registry_context, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, registry, project_root = registry_context
    _, model, scorer, profile = _contract()

    def fail_commit() -> None:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="database unavailable"):
        registry.save(
            model=model,
            risk_scorer=scorer,
            model_family="pump",
            reference_profile=profile,
            training_start_date=date(2026, 8, 1),
            training_end_date=date(2026, 8, 10),
        )

    assert session.query(ModelVersion).count() == 0
    assert list((project_root / "trained_models").rglob("*.*")) == []
