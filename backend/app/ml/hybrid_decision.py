"""Pure, safety-first combination of Stage 7 rules and ML anomaly risk."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable

from app.ml.risk_scoring import AnomalyRiskLevel, AnomalyRiskResult
from app.services.monitoring_rules import DEFAULT_MONITORING_RULES
from app.utils.enums import AlarmSeverity, AnomalyType

logger = logging.getLogger(__name__)


class HybridDecisionSource(str, Enum):
    RULE = "RULE"
    MODEL = "MODEL"
    HYBRID = "HYBRID"
    DATA_QUALITY = "DATA_QUALITY"
    NONE = "NONE"


class HybridReasonCode(str, Enum):
    RULE_LIMIT_EXCEEDED = "RULE_LIMIT_EXCEEDED"
    ML_HIGH_ANOMALY_SCORE = "ML_HIGH_ANOMALY_SCORE"
    ML_CRITICAL_ANOMALY_SCORE = "ML_CRITICAL_ANOMALY_SCORE"
    RULE_AND_MODEL_AGREE = "RULE_AND_MODEL_AGREE"
    LOW_DATA_QUALITY = "LOW_DATA_QUALITY"
    MODEL_INFERENCE_FAILED = "MODEL_INFERENCE_FAILED"


@dataclass(frozen=True)
class HybridDecisionConfig:
    """Explicit thresholds, expressed through the existing risk-level domain."""

    minimum_quality_for_ml: float = float(DEFAULT_MONITORING_RULES.quality_minimum_score)
    model_early_warning_level: AnomalyRiskLevel = AnomalyRiskLevel.HIGH
    model_escalation_level: AnomalyRiskLevel = AnomalyRiskLevel.CRITICAL
    data_quality_severity: AlarmSeverity = AlarmSeverity.MEDIUM


@dataclass(frozen=True)
class HybridAnomalyDecision:
    """A structured alarm candidate; this class never creates a DB alarm."""

    is_anomaly: bool
    decision_source: HybridDecisionSource
    severity: AlarmSeverity | None
    anomaly_type: AnomalyType | None
    risk_score: float | None
    risk_level: AnomalyRiskLevel | None
    model_outlier: bool | None
    rule_triggered: bool
    triggered_rule_codes: tuple[str, ...]
    data_quality_limited: bool
    reason_codes: tuple[HybridReasonCode, ...]
    model_error: bool = False


class HybridDecisionEngine:
    """Make deterministic decisions while ensuring rules always retain priority."""

    def __init__(self, config: HybridDecisionConfig | None = None) -> None:
        self.config = config or HybridDecisionConfig()

    def decide(
        self,
        *,
        rule_severity: AlarmSeverity | None = None,
        triggered_rule_codes: tuple[str, ...] = (),
        rule_anomaly_type: AnomalyType | None = None,
        risk_result: AnomalyRiskResult | None = None,
        data_quality_score: float | None = None,
        entity_family: str | None = None,
    ) -> HybridAnomalyDecision:
        """Combine pre-evaluated Stage 7 rule facts with optional ML risk."""

        rule_triggered = rule_severity is not None or bool(triggered_rule_codes)
        if rule_triggered and rule_severity is None:
            raise ValueError("rule_severity is required when rule codes are supplied.")
        low_quality = (
            data_quality_score is not None
            and data_quality_score < self.config.minimum_quality_for_ml
        )
        if low_quality:
            return self._low_quality_decision(
                rule_severity, triggered_rule_codes, rule_anomaly_type, risk_result
            )
        if rule_triggered:
            return self._rule_decision(
                rule_severity, triggered_rule_codes, rule_anomaly_type, risk_result
            )
        if risk_result is not None and self._is_ml_warning(risk_result.risk_level):
            return HybridAnomalyDecision(
                is_anomaly=True, decision_source=HybridDecisionSource.MODEL,
                severity=self._model_severity(risk_result.risk_level),
                anomaly_type=self._model_anomaly_type(entity_family),
                risk_score=risk_result.risk_score, risk_level=risk_result.risk_level,
                model_outlier=risk_result.model_outlier, rule_triggered=False,
                triggered_rule_codes=(), data_quality_limited=False,
                reason_codes=(self._model_reason(risk_result.risk_level),),
            )
        return self._none_decision(risk_result)

    def decide_with_model(
        self,
        *,
        risk_supplier: Callable[[], AnomalyRiskResult],
        rule_severity: AlarmSeverity | None = None,
        triggered_rule_codes: tuple[str, ...] = (),
        rule_anomaly_type: AnomalyType | None = None,
        data_quality_score: float | None = None,
        entity_family: str | None = None,
    ) -> HybridAnomalyDecision:
        """Contain model failures so Stage 7 rule monitoring remains available."""

        try:
            risk_result = risk_supplier()
        except Exception:
            logger.exception("Hybrid ML inference failed; retaining rule-only monitoring.")
            decision = self.decide(
                rule_severity=rule_severity, triggered_rule_codes=triggered_rule_codes,
                rule_anomaly_type=rule_anomaly_type, data_quality_score=data_quality_score,
                entity_family=entity_family,
            )
            return replace(
                decision, model_error=True,
                reason_codes=(*decision.reason_codes, HybridReasonCode.MODEL_INFERENCE_FAILED),
            )
        return self.decide(
            rule_severity=rule_severity, triggered_rule_codes=triggered_rule_codes,
            rule_anomaly_type=rule_anomaly_type, risk_result=risk_result,
            data_quality_score=data_quality_score, entity_family=entity_family,
        )

    def _low_quality_decision(
        self,
        rule_severity: AlarmSeverity | None,
        rule_codes: tuple[str, ...],
        rule_type: AnomalyType | None,
        risk: AnomalyRiskResult | None,
    ) -> HybridAnomalyDecision:
        if rule_severity is not None:
            # A bad model input cannot suppress an existing safety rule.
            return HybridAnomalyDecision(
                True, HybridDecisionSource.RULE, rule_severity, rule_type,
                self._risk_score(risk), self._risk_level(risk), self._outlier(risk),
                True, rule_codes, True,
                (HybridReasonCode.RULE_LIMIT_EXCEEDED, HybridReasonCode.LOW_DATA_QUALITY),
            )
        return HybridAnomalyDecision(
            True, HybridDecisionSource.DATA_QUALITY, self.config.data_quality_severity,
            AnomalyType.DATA_QUALITY_ANOMALY, self._risk_score(risk), self._risk_level(risk),
            self._outlier(risk), False, (), True, (HybridReasonCode.LOW_DATA_QUALITY,),
        )

    def _rule_decision(
        self,
        rule_severity: AlarmSeverity | None,
        rule_codes: tuple[str, ...],
        rule_type: AnomalyType | None,
        risk: AnomalyRiskResult | None,
    ) -> HybridAnomalyDecision:
        assert rule_severity is not None
        if risk is not None and self._is_ml_warning(risk.risk_level):
            severity = self._escalate(rule_severity, risk.risk_level)
            return HybridAnomalyDecision(
                True, HybridDecisionSource.HYBRID, severity, rule_type,
                risk.risk_score, risk.risk_level, risk.model_outlier, True, rule_codes, False,
                (HybridReasonCode.RULE_LIMIT_EXCEEDED, self._model_reason(risk.risk_level), HybridReasonCode.RULE_AND_MODEL_AGREE),
            )
        return HybridAnomalyDecision(
            True, HybridDecisionSource.RULE, rule_severity, rule_type,
            self._risk_score(risk), self._risk_level(risk), self._outlier(risk), True,
            rule_codes, False, (HybridReasonCode.RULE_LIMIT_EXCEEDED,),
        )

    @staticmethod
    def _none_decision(risk: AnomalyRiskResult | None) -> HybridAnomalyDecision:
        return HybridAnomalyDecision(
            False, HybridDecisionSource.NONE, None, None,
            HybridDecisionEngine._risk_score(risk), HybridDecisionEngine._risk_level(risk),
            HybridDecisionEngine._outlier(risk), False, (), False, (),
        )

    def _is_ml_warning(self, level: AnomalyRiskLevel) -> bool:
        return self._risk_rank(level) >= self._risk_rank(self.config.model_early_warning_level)

    def _escalate(self, severity: AlarmSeverity, level: AnomalyRiskLevel) -> AlarmSeverity:
        if level != self.config.model_escalation_level:
            return severity
        return tuple(AlarmSeverity)[
            min(self._severity_rank(severity) + 1, self._severity_rank(AlarmSeverity.CRITICAL))
        ]

    @staticmethod
    def _model_severity(level: AnomalyRiskLevel) -> AlarmSeverity:
        return AlarmSeverity.HIGH if level == AnomalyRiskLevel.CRITICAL else AlarmSeverity.MEDIUM

    @staticmethod
    def _model_anomaly_type(entity_family: str | None) -> AnomalyType | None:
        return {
            "pump": AnomalyType.EQUIPMENT_ANOMALY,
            "tank": AnomalyType.SENSOR_ANOMALY,
        }.get(entity_family)

    @staticmethod
    def _model_reason(level: AnomalyRiskLevel) -> HybridReasonCode:
        return HybridReasonCode.ML_CRITICAL_ANOMALY_SCORE if level == AnomalyRiskLevel.CRITICAL else HybridReasonCode.ML_HIGH_ANOMALY_SCORE

    @staticmethod
    def _risk_rank(level: AnomalyRiskLevel) -> int:
        return tuple(AnomalyRiskLevel).index(level)

    @staticmethod
    def _severity_rank(severity: AlarmSeverity) -> int:
        return tuple(AlarmSeverity).index(severity)

    @staticmethod
    def _risk_score(risk: AnomalyRiskResult | None) -> float | None:
        return None if risk is None else risk.risk_score

    @staticmethod
    def _risk_level(risk: AnomalyRiskResult | None) -> AnomalyRiskLevel | None:
        return None if risk is None else risk.risk_level

    @staticmethod
    def _outlier(risk: AnomalyRiskResult | None) -> bool | None:
        return None if risk is None else risk.model_outlier
