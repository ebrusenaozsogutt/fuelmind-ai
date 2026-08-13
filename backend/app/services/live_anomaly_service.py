"""Live inference orchestration for persisted sensor samples."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta
from time import perf_counter

import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import NotFoundError
from app.ml.explainability import AnomalyExplanationService
from app.ml.feature_engineering import AnomalyFeatureEngineer
from app.ml.hybrid_decision import HybridDecisionEngine
from app.ml.model_registry import AnomalyModelRegistry, NoActiveModelError
from app.repositories.sensor_reading_repository import SensorReadingRepository
from app.schemas.live_anomaly import LiveAiState, LiveAnomalyResult
from app.services.alarm_engine import RuleAlarmCandidate
from app.services.alarm_templates import guidance_for
from app.utils.enums import AlarmSeverity, AnomalyType

logger = logging.getLogger(__name__)

_RULE_TYPES = {
    "LOW_FLOW": AnomalyType.EQUIPMENT_ANOMALY,
    "HIGH_MOTOR_CURRENT": AnomalyType.EQUIPMENT_ANOMALY,
    "HIGH_PRESSURE": AnomalyType.EQUIPMENT_ANOMALY,
    "HIGH_WATER_LEVEL": AnomalyType.SENSOR_ANOMALY,
    "SENSOR_STUCK": AnomalyType.DATA_QUALITY_ANOMALY,
    "SENSOR_SPIKE": AnomalyType.DATA_QUALITY_ANOMALY,
    "LOW_DATA_QUALITY": AnomalyType.DATA_QUALITY_ANOMALY,
    "TANK_SALES_MISMATCH": AnomalyType.SENSOR_ANOMALY,
}


class LiveAnomalyService:
    """Reuse training feature formulas and cached active artifacts for live samples."""

    def __init__(self, db: Session, *, registry: AnomalyModelRegistry | None = None) -> None:
        self.db = db
        self._registry = registry or AnomalyModelRegistry(db)
        self._readings = SensorReadingRepository(db)
        self._features = AnomalyFeatureEngineer()
        self._hybrid = HybridDecisionEngine()
        self._explanations = AnomalyExplanationService()

    def evaluate(
        self,
        readings: list[object],
        rule_candidates: list[RuleAlarmCandidate],
    ) -> list[LiveAnomalyResult]:
        grouped: dict[tuple[str, int], list[RuleAlarmCandidate]] = defaultdict(list)
        for candidate in rule_candidates:
            grouped[(candidate.target_type, candidate.target_id)].append(candidate)

        results = []
        for reading in readings:
            family = "pump" if getattr(reading, "pump_id", None) is not None else "tank"
            entity_id = int(reading.pump_id if family == "pump" else reading.tank_id)
            results.append(
                self._evaluate_one(reading, family, grouped.get((family.upper(), entity_id), []))
            )
        return results

    def _evaluate_one(
        self,
        reading: object,
        family: str,
        candidates: list[RuleAlarmCandidate],
    ) -> LiveAnomalyResult:
        started = perf_counter()
        entity_id = int(reading.pump_id if family == "pump" else reading.tank_id)
        rule_codes = tuple(dict.fromkeys(item.alarm_type for item in candidates))
        rule_severity = self._highest_severity(candidates)
        rule_type = next((_RULE_TYPES.get(code) for code in rule_codes if code in _RULE_TYPES), None)
        quality_score = float(reading.data_quality_score)

        try:
            artifact = self._registry.get_active(family)  # registry owns the process-wide artifact cache
        except (NoActiveModelError, NotFoundError):
            decision = self._hybrid.decide(
                rule_severity=rule_severity, triggered_rule_codes=rule_codes,
                rule_anomaly_type=rule_type, data_quality_score=quality_score,
                entity_family=family,
            )
            return self._without_model(reading, family, entity_id, decision, LiveAiState.NO_ACTIVE_MODEL)
        except Exception:
            logger.exception("Active live AI model could not be loaded: family=%s entity_id=%s", family, entity_id)
            decision = self._hybrid.decide(
                rule_severity=rule_severity, triggered_rule_codes=rule_codes,
                rule_anomaly_type=rule_type, data_quality_score=quality_score,
                entity_family=family,
            )
            return self._without_model(reading, family, entity_id, decision, LiveAiState.UNAVAILABLE)

        feature_row = self._live_feature_row(reading, family)
        if feature_row is None:
            decision = self._hybrid.decide(
                rule_severity=rule_severity, triggered_rule_codes=rule_codes,
                rule_anomaly_type=rule_type, data_quality_score=quality_score,
                entity_family=family,
            )
            return self._result(
                reading, family, entity_id, LiveAiState.WARMING_UP, decision,
                model_version=artifact.registry_version,
                data_quality_note="AI is collecting sufficient feature history; rule monitoring remains active.",
                guidance_codes=rule_codes,
            )

        try:
            risk = artifact.risk_scorer.score_features(artifact.model, feature_row)[0]
            decision = self._hybrid.decide(
                rule_severity=rule_severity, triggered_rule_codes=rule_codes,
                rule_anomaly_type=rule_type, risk_result=risk,
                data_quality_score=quality_score, entity_family=family,
            )
            explanation = self._explanations.explain(
                decision, feature_row.iloc[-1], artifact.reference_profile,
                quality_flags=tuple(getattr(reading, "quality_flags_json", ())),
            )
            elapsed_ms = (perf_counter() - started) * 1000
            logger.debug(
                "Live AI inference family=%s entity_id=%s model=%s risk=%.2f elapsed_ms=%.2f",
                family, entity_id, artifact.registry_version, risk.risk_score, elapsed_ms,
            )
            return self._result(
                reading, family, entity_id, LiveAiState.READY, decision,
                model_version=artifact.registry_version,
                decision_function=risk.decision_function,
                findings=() if explanation is None else tuple(
                    self._finding_payload(item) for item in explanation.findings
                ),
                probable_causes=() if explanation is None else explanation.probable_causes,
                recommended_checks=() if explanation is None else explanation.recommended_checks,
                data_quality_note=None if explanation is None else explanation.data_quality_note,
                guidance_codes=rule_codes,
            )
        except Exception:
            logger.exception(
                "Live AI inference failed; retaining Stage 7 rules: family=%s entity_id=%s model=%s",
                family, entity_id, artifact.registry_version,
            )
            decision = self._hybrid.decide(
                rule_severity=rule_severity, triggered_rule_codes=rule_codes,
                rule_anomaly_type=rule_type, data_quality_score=quality_score,
                entity_family=family,
            )
            return self._result(
                reading, family, entity_id, LiveAiState.UNAVAILABLE, decision,
                model_version=artifact.registry_version,
                data_quality_note="AI inference is temporarily unavailable; rule monitoring remains active.",
                guidance_codes=rule_codes,
            )

    def _live_feature_row(self, current: object, family: str) -> pd.DataFrame | None:
        moment = current.reading_timestamp
        history = self._readings.history(
            station_id=current.station_id,
            tank_id=None if family == "pump" else current.tank_id,
            pump_id=current.pump_id if family == "pump" else None,
            from_time=moment - timedelta(minutes=settings.LIVE_AI_HISTORY_MINUTES),
            to_time=moment,
            limit=settings.LIVE_AI_HISTORY_LIMIT,
        )
        rows = [self._reading_row(item) for item in history if item is not current]
        rows.append(self._reading_row(current))
        engineered = self._features.engineer(pd.DataFrame(rows))
        features = engineered.features[family]
        metadata = engineered.metadata[family]
        if features.empty:
            return None
        entity_column = "pump_id" if family == "pump" else "tank_id"
        entity_id = getattr(current, entity_column)
        current_time = pd.Timestamp(moment)
        matches = metadata.index[
            (metadata[entity_column] == entity_id)
            & (metadata["reading_timestamp"] == current_time)
        ]
        return None if len(matches) == 0 else features.loc[[matches[-1]]].reset_index(drop=True)

    @staticmethod
    def _reading_row(reading: object) -> dict[str, object]:
        columns = (
            "reading_timestamp", "station_id", "tank_id", "pump_id", "simulation_run_id",
            "sequence_number", "source_type", "flow_rate", "pressure", "motor_current",
            "pump_temperature", "error_count", "working_duration", "data_quality_score",
            "tank_level", "true_tank_level", "temperature", "water_level",
        )
        row = {name: getattr(reading, name, None) for name in columns}
        source = row["source_type"]
        row["source_type"] = getattr(source, "value", source)
        return row

    @staticmethod
    def _highest_severity(candidates: list[RuleAlarmCandidate]) -> AlarmSeverity | None:
        if not candidates:
            return None
        ranks = {severity: index for index, severity in enumerate(AlarmSeverity)}
        return max((item.severity for item in candidates), key=ranks.__getitem__)

    def _without_model(self, reading, family, entity_id, decision, state) -> LiveAnomalyResult:
        note = (
            "No active anomaly model is available; rule monitoring remains active."
            if state is LiveAiState.NO_ACTIVE_MODEL
            else "AI is temporarily unavailable; rule monitoring remains active."
        )
        return self._result(
            reading, family, entity_id, state, decision,
            data_quality_note=note, guidance_codes=decision.triggered_rule_codes,
        )

    @staticmethod
    def _finding_payload(finding: object) -> dict[str, object]:
        """Serialize an explainability finding without discarding numeric evidence."""

        return {
            "feature_name": finding.feature_name,
            "display_name": finding.display_name,
            "current_value": finding.current_value,
            "reference_value": finding.reference_value,
            "absolute_difference": finding.absolute_difference,
            "percent_difference": finding.percent_difference,
            "direction": finding.direction,
            "message": finding.message,
        }

    @staticmethod
    def _result(
        reading, family, entity_id, state, decision, *, model_version=None,
        decision_function=None, findings=(), probable_causes=(), recommended_checks=(),
        data_quality_note=None, guidance_codes=(),
    ) -> LiveAnomalyResult:
        if not probable_causes or not recommended_checks:
            causes, checks = [], []
            for code in guidance_codes:
                _, recommendation, probable = guidance_for(code)
                causes.extend(item["description"] for item in probable)
                checks.append(recommendation)
            probable_causes = probable_causes or tuple(dict.fromkeys(causes))
            recommended_checks = recommended_checks or tuple(dict.fromkeys(checks))
        return LiveAnomalyResult(
            entity_type=family.upper(), entity_id=entity_id, station_id=reading.station_id,
            timestamp=reading.reading_timestamp, ai_state=state,
            risk_score=decision.risk_score,
            risk_level=None if decision.risk_level is None else decision.risk_level.value,
            decision_source=decision.decision_source.value,
            severity=None if decision.severity is None else decision.severity.value,
            anomaly_type=None if decision.anomaly_type is None else decision.anomaly_type.value,
            model_outlier=decision.model_outlier,
            triggered_rules=decision.triggered_rule_codes,
            findings=tuple(findings), probable_causes=tuple(probable_causes),
            recommended_checks=tuple(recommended_checks), data_quality_note=data_quality_note,
            model_version=model_version, decision_function=decision_function,
        )
