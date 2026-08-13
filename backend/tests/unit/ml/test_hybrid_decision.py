"""Safety-first tests for Stage 8.5 hybrid anomaly decisions."""

from __future__ import annotations

import logging

import pytest

from app.ml.hybrid_decision import (
    HybridDecisionEngine, HybridDecisionSource, HybridReasonCode,
)
from app.ml.risk_scoring import AnomalyRiskLevel, AnomalyRiskResult
from app.utils.enums import AlarmSeverity, AnomalyType


def _risk(level: AnomalyRiskLevel, score: float) -> AnomalyRiskResult:
    return AnomalyRiskResult(1 if level in {AnomalyRiskLevel.NORMAL, AnomalyRiskLevel.WATCH} else -1, 0.1, -0.4, score, level, level not in {AnomalyRiskLevel.NORMAL, AnomalyRiskLevel.WATCH})


def test_model_only_normal_and_watch_do_not_create_anomaly() -> None:
    engine = HybridDecisionEngine()
    for level, score in ((AnomalyRiskLevel.NORMAL, 14), (AnomalyRiskLevel.WATCH, 35)):
        decision = engine.decide(risk_result=_risk(level, score))
        assert not decision.is_anomaly and decision.decision_source is HybridDecisionSource.NONE


def test_model_high_and_critical_create_early_warnings() -> None:
    engine = HybridDecisionEngine()
    high = engine.decide(risk_result=_risk(AnomalyRiskLevel.HIGH, 78), entity_family="pump")
    critical = engine.decide(risk_result=_risk(AnomalyRiskLevel.CRITICAL, 92), entity_family="tank")

    assert high.decision_source is HybridDecisionSource.MODEL and high.severity is AlarmSeverity.MEDIUM
    assert high.anomaly_type is AnomalyType.EQUIPMENT_ANOMALY
    assert critical.severity is AlarmSeverity.HIGH and critical.anomaly_type is AnomalyType.SENSOR_ANOMALY


def test_rules_are_never_overridden_and_codes_are_preserved() -> None:
    engine = HybridDecisionEngine()
    warning = engine.decide(rule_severity=AlarmSeverity.HIGH, triggered_rule_codes=("LOW_FLOW",), rule_anomaly_type=AnomalyType.EQUIPMENT_ANOMALY, risk_result=_risk(AnomalyRiskLevel.NORMAL, 18))
    critical = engine.decide(rule_severity=AlarmSeverity.CRITICAL, triggered_rule_codes=("HIGH_WATER_LEVEL",), risk_result=_risk(AnomalyRiskLevel.NORMAL, 12))

    assert warning.decision_source is HybridDecisionSource.RULE and warning.severity is AlarmSeverity.HIGH
    assert warning.triggered_rule_codes == ("LOW_FLOW",)
    assert critical.severity is AlarmSeverity.CRITICAL


def test_rule_plus_model_is_hybrid_and_critical_risk_can_escalate() -> None:
    decision = HybridDecisionEngine().decide(
        rule_severity=AlarmSeverity.MEDIUM, triggered_rule_codes=("LOW_FLOW",),
        rule_anomaly_type=AnomalyType.EQUIPMENT_ANOMALY,
        risk_result=_risk(AnomalyRiskLevel.CRITICAL, 93),
    )

    assert decision.decision_source is HybridDecisionSource.HYBRID
    assert decision.severity is AlarmSeverity.HIGH
    assert HybridReasonCode.RULE_AND_MODEL_AGREE in decision.reason_codes


def test_low_quality_limits_model_but_never_suppresses_rule() -> None:
    engine = HybridDecisionEngine()
    quality = engine.decide(risk_result=_risk(AnomalyRiskLevel.CRITICAL, 95), data_quality_score=30)
    rule = engine.decide(rule_severity=AlarmSeverity.CRITICAL, triggered_rule_codes=("HIGH_WATER_LEVEL",), risk_result=_risk(AnomalyRiskLevel.NORMAL, 12), data_quality_score=30)

    assert quality.decision_source is HybridDecisionSource.DATA_QUALITY and quality.data_quality_limited
    assert rule.decision_source is HybridDecisionSource.RULE and rule.severity is AlarmSeverity.CRITICAL


def test_rule_only_none_and_model_error_are_safe(caplog: pytest.LogCaptureFixture) -> None:
    engine = HybridDecisionEngine()
    rule = engine.decide(rule_severity=AlarmSeverity.HIGH, triggered_rule_codes=("LOW_FLOW",))
    none = engine.decide()
    with caplog.at_level(logging.ERROR):
        failed = engine.decide_with_model(
            risk_supplier=lambda: (_ for _ in ()).throw(RuntimeError("model unavailable")),
            rule_severity=AlarmSeverity.HIGH, triggered_rule_codes=("LOW_FLOW",),
        )

    assert rule.decision_source is HybridDecisionSource.RULE
    assert none.decision_source is HybridDecisionSource.NONE
    assert failed.decision_source is HybridDecisionSource.RULE and failed.model_error
    assert HybridReasonCode.MODEL_INFERENCE_FAILED in failed.reason_codes
    assert "Hybrid ML inference failed" in caplog.text


def test_same_input_is_deterministic() -> None:
    engine = HybridDecisionEngine()
    values = dict(rule_severity=AlarmSeverity.HIGH, triggered_rule_codes=("LOW_FLOW",), risk_result=_risk(AnomalyRiskLevel.HIGH, 78))
    assert engine.decide(**values) == engine.decide(**values)
