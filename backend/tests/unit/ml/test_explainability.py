"""Tests for deterministic, baseline-based hybrid decision explanations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.explainability import AnomalyExplanationService
from app.ml.hybrid_decision import HybridDecisionEngine
from app.ml.risk_scoring import AnomalyRiskLevel, AnomalyRiskResult
from app.utils.enums import AlarmSeverity, AnomalyType


def _profile():
    return AnomalyExplanationService().fit_reference(pd.DataFrame({
        "flow_rate": [39, 40, 41, 42, 43], "motor_current": [9, 10, 10, 11, 11],
        "water_level": [0, 0, 0, 0, 0],
    }), family="pump")


def _risk(level=AnomalyRiskLevel.HIGH, score=81):
    return AnomalyRiskResult(-1, -0.1, -0.6, score, level, True)


def test_reference_profile_deviation_ranking_and_display_names() -> None:
    service = AnomalyExplanationService()
    decision = HybridDecisionEngine().decide(risk_result=_risk(), entity_family="pump")
    explanation = service.explain(decision, {"flow_rate": 24, "motor_current": 15, "water_level": 0}, _profile())

    assert explanation is not None
    assert explanation.findings[0].feature_name == "flow_rate"
    assert explanation.findings[0].display_name == "Pompa debisi"
    assert explanation.findings[0].percent_difference == pytest.approx(-41.46, abs=0.01)
    assert "kesin bir arıza teşhisi değildir" in explanation.summary


def test_rule_hybrid_guidance_and_low_quality_note_are_preserved() -> None:
    service = AnomalyExplanationService()
    decision = HybridDecisionEngine().decide(
        rule_severity=AlarmSeverity.HIGH, triggered_rule_codes=("LOW_FLOW", "HIGH_MOTOR_CURRENT"),
        rule_anomaly_type=AnomalyType.EQUIPMENT_ANOMALY, risk_result=_risk(AnomalyRiskLevel.CRITICAL, 94),
    )
    explanation = service.explain(decision, {"flow_rate": 24, "motor_current": 15, "water_level": 0}, _profile())
    low_quality = HybridDecisionEngine().decide(risk_result=_risk(), data_quality_score=30)
    quality_explanation = service.explain(low_quality, {"flow_rate": 24, "motor_current": 15, "water_level": 0}, _profile(), quality_flags=("SENSOR_STUCK",))

    assert explanation is not None and len(explanation.rule_evidence) == 2
    assert "Filtre tıkanıklığı" in explanation.probable_causes
    assert quality_explanation is not None and "güvenilirliği düşük" in quality_explanation.data_quality_note


def test_zero_median_finding_is_operationally_meaningful() -> None:
    service = AnomalyExplanationService()
    decision = HybridDecisionEngine().decide(risk_result=_risk(), entity_family="pump")
    profile = service.fit_reference(pd.DataFrame({"flow_rate_change_5min": [-1, 0, 0, 0, 1]}), family="pump")

    explanation = service.explain(decision, {"flow_rate_change_5min": 7}, profile)

    assert explanation is not None
    assert "olağan davranış aralığının üzerinde" in explanation.findings[0].message
    assert "0.00" not in explanation.findings[0].message
    assert "normal median" not in explanation.findings[0].message


def test_none_returns_no_explanation_and_invalid_data_is_rejected() -> None:
    service = AnomalyExplanationService()
    assert service.explain(HybridDecisionEngine().decide(), {"flow_rate": 40, "motor_current": 10, "water_level": 0}, _profile()) is None
    with pytest.raises(ValueError, match="NaN or infinity"):
        service.fit_reference(pd.DataFrame({"x": [1, np.nan]}), family="pump")
    decision = HybridDecisionEngine().decide(risk_result=_risk())
    with pytest.raises(ValueError, match="NaN or infinity"):
        service.explain(decision, {"flow_rate": np.nan, "motor_current": 10, "water_level": 0}, _profile())
