from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.live.serializers import (
    serialize_alarm_created,
    serialize_anomaly_evaluation,
    serialize_simulation_tick,
)
from app.schemas.live_anomaly import LiveAiState, LiveAnomalyResult
from app.simulation.tick_result import SimulationTickResult


def test_simulation_tick_adds_ai_results_without_changing_existing_contract() -> None:
    moment = datetime(2026, 8, 12, tzinfo=timezone.utc)
    tick = SimulationTickResult(1, moment, 7)
    tick.ai_results = [LiveAnomalyResult(
        entity_type="PUMP", entity_id=4, station_id=1, timestamp=moment,
        ai_state=LiveAiState.READY, risk_score=91, risk_level="CRITICAL",
        decision_source="HYBRID", severity="CRITICAL", model_version="v0001",
    )]
    payload = serialize_simulation_tick(8, tick, generated_at=moment)
    assert payload["event_type"] == "simulation_tick"
    assert {"tanks", "pumps", "sales", "events", "active_scenarios"} <= payload.keys()
    assert "ai_results" not in payload
    ai_payload = serialize_anomaly_evaluation(8, tick)
    assert ai_payload["event_type"] == "anomaly_evaluation"
    assert ai_payload["results"][0]["risk_score"] == 91
    assert ai_payload["results"][0]["model_version"] == "v0001"


def test_alarm_created_exposes_complete_persisted_ai_contract() -> None:
    moment = datetime(2026, 8, 12, tzinfo=timezone.utc)
    alarm = SimpleNamespace(
        id=14, station_id=1, tank_id=None, pump_id=4,
        alarm_type="LOW_FLOW", severity=SimpleNamespace(value="CRITICAL"),
        title="Low Flow", description="Flow is below normal.",
        anomaly_type="EQUIPMENT_ANOMALY", recommended_action="Check filter.",
        probable_causes=[{"description": "Filter restriction"}],
        anomaly_score=Decimal("91.25"), risk_level="CRITICAL",
        decision_source="HYBRID", model_version="v0001", model_outlier=True,
        triggered_rules_json=["LOW_FLOW"], findings_json=[{
            "feature_name": "flow_rate", "display_name": "Pompa debisi",
            "current_value": 24.3, "reference_value": 42.1,
            "percent_difference": -42.3, "direction": "LOW",
            "message": "Pompa debisi normal medyanın yaklaşık %42.3 altında.",
        }],
        recommended_checks_json=["Check the pump filter."], data_quality_note=None,
        status=SimpleNamespace(value="NEW"), detected_at=moment,
    )

    payload = serialize_alarm_created(alarm)

    assert payload["anomaly_score"] == 91.25
    assert payload["risk_level"] == "CRITICAL"
    assert payload["decision_source"] == "HYBRID"
    assert payload["anomaly_type"] == "EQUIPMENT_ANOMALY"
    assert payload["model_version"] == "v0001"
    assert payload["model_outlier"] is True
    assert payload["triggered_rules"] == ["LOW_FLOW"]
    assert payload["findings"][0]["current_value"] == 24.3
    assert payload["findings"][0]["percent_difference"] == -42.3
