"""Stage 7 quality and rule-alarm behaviour."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.alarm_engine import AlarmEngine
from app.services.data_quality_service import DataQualityService
from app.utils.enums import AlarmStatus

T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def reading(**overrides):
    values = dict(tank_id=1, pump_id=None, reading_timestamp=T, tank_level=100, true_tank_level=100, flow_rate=None, pressure=None, motor_current=None, water_level=0, data_quality_score=100, quality_flags_json=[])
    values.update(overrides)
    return SimpleNamespace(**values)


class Repo:
    def __init__(self): self.items = []
    def active_for_key(self, station, typ, target, alarm_type):
        return next((x for x in self.items if x.station_id == station and x.target_type == typ and x.target_id == target and x.alarm_type == alarm_type and x.status in {AlarmStatus.NEW, AlarmStatus.ACKNOWLEDGED, AlarmStatus.INVESTIGATING}), None)
    def create(self, values):
        item = SimpleNamespace(**values, target_type="TANK" if values["tank_id"] else "PUMP", target_id=values["tank_id"] or values["pump_id"])
        self.items.append(item)
        return item


def tank(**kw): return SimpleNamespace(tank_id=1, water_level=kw.get("water", 0))
def pump(**kw): return SimpleNamespace(pump_id=2, is_active_status=kw.get("active", True), flow_rate=kw.get("flow", 20), minimum_flow_rate=10, motor_current=kw.get("current", 5), maximum_motor_current=10, pressure=kw.get("pressure", 5), maximum_pressure=8)
def evaluate(repo, *, tanks=None, pumps=None, readings=None, deliveries=None):
    return AlarmEngine(repo).evaluate(station_id=1, tanks=tanks or [], pumps=pumps or [], readings=readings or [], moment=T, delivery_tank_ids=deliveries)


def test_quality_flags_and_central_penalties():
    assessment = DataQualityService().assess(reading(tank_level=100, true_tank_level=100), previous=reading(reading_timestamp=T - timedelta(seconds=301), tank_level=100, true_tank_level=110), capacity_liters=1000, expected_sale_change=1)
    assert {"COMMUNICATION_GAP", "SENSOR_STUCK", "TANK_SALES_MISMATCH"} <= set(assessment.flags)
    assert assessment.score < 100


def test_pump_and_water_alarm_rules_and_idle_exception():
    repo = Repo()
    pump_reading = reading(tank_id=1, pump_id=2)
    evaluate(repo, tanks=[tank(water=6)], pumps=[pump(flow=5, current=11, pressure=9)], readings=[reading(), pump_reading])
    assert {x.alarm_type for x in repo.items} == {"HIGH_WATER_LEVEL", "LOW_FLOW", "HIGH_MOTOR_CURRENT", "HIGH_PRESSURE"}
    idle = Repo()
    evaluate(idle, pumps=[pump(active=False, flow=0)], readings=[pump_reading])
    assert not idle.items


def test_rule_alarms_include_differentiated_operational_guidance():
    repo = Repo()
    evaluate(repo, pumps=[pump(flow=5)], readings=[reading(tank_id=1, pump_id=2)])
    alarm = repo.items[0]
    assert alarm.alarm_type == "LOW_FLOW"
    assert alarm.title == "Pompa Debi Düşüşü"
    assert "debi" in alarm.description.lower()
    assert "pompa filtresini" in alarm.recommended_action.lower()
    assert len(alarm.probable_causes) == 3


def test_quality_stuck_mismatch_delivery_and_deduplication():
    repo = Repo()
    low = reading(data_quality_score=20, quality_flags_json=["SENSOR_STUCK", "TANK_SALES_MISMATCH", "SENSOR_SPIKE"])
    evaluate(repo, tanks=[tank()], readings=[low], deliveries={1})
    assert {x.alarm_type for x in repo.items} == {"LOW_DATA_QUALITY", "SENSOR_STUCK", "TANK_SALES_MISMATCH"}
    evaluate(repo, tanks=[tank()], readings=[low], deliveries={1})
    assert len(repo.items) == 3
    repo.items[0].status = AlarmStatus.RESOLVED
    evaluate(repo, tanks=[tank()], readings=[low], deliveries={1})
    assert len(repo.items) == 4


def test_rule_only_alarm_keeps_ai_contract_empty_and_dedup_unchanged():
    repo = Repo()
    evaluate(repo, pumps=[pump(flow=5)], readings=[reading(tank_id=1, pump_id=2)])

    alarm = repo.items[0]
    assert alarm.decision_source is None
    assert alarm.risk_level is None
    assert alarm.model_version is None
    assert alarm.findings_json == []
    assert alarm.recommended_checks_json == []
    evaluate(repo, pumps=[pump(flow=5)], readings=[reading(tank_id=1, pump_id=2)])
    assert len(repo.items) == 1


def test_hybrid_alarm_persists_complete_real_ai_detail():
    repo = Repo()
    candidate = AlarmEngine(repo).candidates(
        station_id=1,
        tanks=[],
        pumps=[pump(flow=5, current=11)],
        readings=[reading(tank_id=1, pump_id=2)],
        moment=T,
    )[0]
    ai_result = SimpleNamespace(
        risk_score=91.25,
        risk_level="CRITICAL",
        decision_source="HYBRID",
        severity="CRITICAL",
        anomaly_type="EQUIPMENT_ANOMALY",
        model_version="v0001",
        model_outlier=True,
        triggered_rules=("LOW_FLOW", "HIGH_MOTOR_CURRENT"),
        findings=("Pump flow rate is 43% below normal.",),
        probable_causes=("Filter restriction",),
        recommended_checks=("Check the pump filter.",),
        data_quality_note=None,
        is_anomaly=True,
    )

    alarm = AlarmEngine(repo).raise_candidates(
        [candidate], {("PUMP", 2): ai_result}
    )[0]

    assert alarm.anomaly_score == 91.25
    assert alarm.risk_level == "CRITICAL"
    assert alarm.decision_source == "HYBRID"
    assert alarm.anomaly_type == "EQUIPMENT_ANOMALY"
    assert alarm.model_version == "v0001"
    assert alarm.model_outlier is True
    assert alarm.triggered_rules_json == ["LOW_FLOW", "HIGH_MOTOR_CURRENT"]
    assert alarm.findings_json == ["Pump flow rate is 43% below normal."]
    assert alarm.probable_causes == [{"description": "Filter restriction"}]
    assert alarm.recommended_checks_json == ["Check the pump filter."]


def test_structured_ai_findings_are_preserved_without_breaking_alarm_description():
    repo = Repo()
    candidate = AlarmEngine(repo).candidates(
        station_id=1,
        tanks=[],
        pumps=[pump(flow=5)],
        readings=[reading(tank_id=1, pump_id=2)],
        moment=T,
    )[0]
    ai_result = SimpleNamespace(
        risk_score=91.25,
        risk_level="CRITICAL",
        decision_source="MODEL",
        severity="CRITICAL",
        anomaly_type="EQUIPMENT_ANOMALY",
        model_version="v0001",
        model_outlier=True,
        triggered_rules=(),
        findings=({"message": "Pump flow rate is below its learned range."},),
        probable_causes=(),
        recommended_checks=(),
        data_quality_note=None,
        is_anomaly=True,
    )

    alarm = AlarmEngine(repo).raise_candidates(
        [candidate], {("PUMP", 2): ai_result}
    )[0]

    assert "below its learned range" in alarm.description
    assert alarm.findings_json == [{"message": "Pump flow rate is below its learned range."}]
