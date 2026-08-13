"""Controlled Stage 8.9 live scenario validation."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.ml.explainability import FeatureReferenceProfile, FeatureReferenceStats
from app.ml.feature_engineering import PUMP_ANOMALY_FEATURE_NAMES, TANK_ANOMALY_FEATURE_NAMES
from app.ml.model_registry import NoActiveModelError
from app.ml.risk_scoring import AnomalyRiskLevel, AnomalyRiskResult
from app.schemas.live_anomaly import LiveAiState
from app.services.alarm_engine import RuleAlarmCandidate
from app.services.live_anomaly_service import LiveAnomalyService
from app.utils.enums import AlarmSeverity

NOW = datetime(2026, 8, 12, 9, 30, tzinfo=timezone.utc)


class FakeRiskScorer:
    def __init__(self, family: str) -> None:
        self.family = family

    def score_features(self, _model, features):
        row = features.iloc[-1]
        if self.family == "pump":
            risk = 92.0 if row.flow_rate < 10 else 88.0 if row.motor_current > 10 else 10.0
        else:
            risk = 90.0 if abs(row.tank_level - row.true_tank_level) > 50 else 76.0 if row.tank_level_change < -10 else 10.0
        return [AnomalyRiskResult(
            prediction=-1 if risk >= 70 else 1, decision_function=(50 - risk) / 100,
            score_samples=-risk / 100, risk_score=risk,
            risk_level=AnomalyRiskLevel.CRITICAL if risk >= 85 else AnomalyRiskLevel.HIGH if risk >= 70 else AnomalyRiskLevel.NORMAL,
            model_outlier=risk >= 70,
        )]


class FakeRegistry:
    def get_active(self, family: str):
        names = PUMP_ANOMALY_FEATURE_NAMES if family == "pump" else TANK_ANOMALY_FEATURE_NAMES
        stats = {name: FeatureReferenceStats(1, 0, 0.5, 1.5, 2) for name in names}
        return SimpleNamespace(
            registry_version="v0001", model=object(), risk_scorer=FakeRiskScorer(family),
            reference_profile=FeatureReferenceProfile(family, names, stats),
        )


class MissingRegistry:
    def get_active(self, _family: str):
        raise NoActiveModelError("missing")


class BrokenRegistry:
    def get_active(self, _family: str):
        raise RuntimeError("artifact corrupt")


def reading(family: str, minute: int, **overrides):
    values = dict(
        reading_timestamp=NOW + timedelta(minutes=minute), station_id=1,
        tank_id=1, pump_id=4 if family == "pump" else None,
        simulation_run_id=8, sequence_number=minute + 31, source_type="SIMULATION",
        flow_rate=40.0 if family == "pump" else None,
        pressure=5.0 if family == "pump" else None,
        motor_current=6.0 if family == "pump" else None,
        pump_temperature=35.0 if family == "pump" else None,
        error_count=0, working_duration=100 + minute if family == "pump" else None,
        data_quality_score=100.0, tank_level=600.0 if family == "tank" else None,
        true_tank_level=600.0 if family == "tank" else None,
        temperature=22.0 if family == "tank" else None,
        water_level=1.0 if family == "tank" else None, quality_flags_json=[],
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def service_for(family: str, current, registry=None):
    service = LiveAnomalyService(SimpleNamespace(), registry=registry or FakeRegistry())
    history = [reading(family, minute) for minute in range(-31, 0)]
    service._readings = SimpleNamespace(history=lambda **_: history)
    return service


def candidate(code: str, family: str, severity=AlarmSeverity.HIGH):
    return RuleAlarmCandidate(1, family.upper(), 4 if family == "pump" else 1, code, severity, NOW)


def test_normal_pump_has_low_risk_and_no_hybrid_anomaly() -> None:
    current = reading("pump", 0)
    result = service_for("pump", current).evaluate([current], [])[0]
    assert result.ai_state is LiveAiState.READY
    assert result.risk_score == 10
    assert result.risk_level == "NORMAL"
    assert result.decision_source == "NONE"
    assert not result.is_anomaly


@pytest.mark.parametrize(
    ("name", "family", "overrides", "rule_code", "expected_risk", "expected_decision"),
    [
        ("FLOW_DROP", "pump", {"flow_rate": 4.0, "motor_current": 12.0}, "LOW_FLOW", 92, "HYBRID"),
        ("HIGH_MOTOR_CURRENT", "pump", {"motor_current": 14.0}, "HIGH_MOTOR_CURRENT", 88, "HYBRID"),
        ("TANK_LEAK", "tank", {"tank_level": 570.0, "true_tank_level": 570.0}, "TANK_SALES_MISMATCH", 76, "HYBRID"),
        ("SENSOR_STUCK", "tank", {"data_quality_score": 50.0, "quality_flags_json": ["SENSOR_STUCK"]}, "SENSOR_STUCK", 10, "RULE"),
        ("SENSOR_SPIKE", "tank", {"tank_level": 850.0, "data_quality_score": 60.0, "quality_flags_json": ["SENSOR_SPIKE"]}, "SENSOR_SPIKE", 90, "RULE"),
        ("WATER_LEVEL_RISE", "tank", {"water_level": 8.0}, "HIGH_WATER_LEVEL", 10, "RULE"),
        ("DEMAND_SURGE", "pump", {}, None, 10, "NONE"),
    ],
)
def test_controlled_scenario_outcomes(name, family, overrides, rule_code, expected_risk, expected_decision) -> None:
    current = reading(family, 0, **overrides)
    rules = [] if rule_code is None else [candidate(rule_code, family)]
    result = service_for(family, current).evaluate([current], rules)[0]
    assert result.risk_score == expected_risk, name
    assert result.decision_source == expected_decision, name
    assert bool(result.triggered_rules) is (rule_code is not None), name
    if rule_code is not None:
        assert result.probable_causes and result.recommended_checks, name


def test_live_result_keeps_structured_numeric_finding_evidence() -> None:
    current = reading("pump", 0, flow_rate=4.0, motor_current=12.0)

    result = service_for("pump", current).evaluate(
        [current], [candidate("LOW_FLOW", "pump")]
    )[0]

    finding = result.findings[0]
    assert finding["display_name"]
    assert finding["current_value"] != finding["reference_value"]
    assert finding["percent_difference"] is not None
    assert finding["direction"] == (
        "LOW" if finding["current_value"] < finding["reference_value"] else "HIGH"
    )


def test_no_model_and_model_error_keep_rules_available() -> None:
    current = reading("pump", 0, flow_rate=4.0)
    rules = [candidate("LOW_FLOW", "pump")]
    no_model = service_for("pump", current, MissingRegistry()).evaluate([current], rules)[0]
    unavailable = service_for("pump", current, BrokenRegistry()).evaluate([current], rules)[0]
    assert (no_model.ai_state, no_model.decision_source) == (LiveAiState.NO_ACTIVE_MODEL, "RULE")
    assert (unavailable.ai_state, unavailable.decision_source) == (LiveAiState.UNAVAILABLE, "RULE")


def test_insufficient_history_reports_warmup_without_fake_zero_risk() -> None:
    current = reading("pump", 0)
    service = LiveAnomalyService(SimpleNamespace(), registry=FakeRegistry())
    service._readings = SimpleNamespace(history=lambda **_: [])
    result = service.evaluate([current], [])[0]
    assert result.ai_state is LiveAiState.WARMING_UP
    assert result.risk_score is None
    assert result.model_version == "v0001"
