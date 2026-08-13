"""Rule alarm evaluation and active-alarm deduplication."""

from dataclasses import dataclass
from datetime import datetime
from app.repositories.alarm_repository import AlarmRepository
from app.services.monitoring_rules import DEFAULT_MONITORING_RULES, MonitoringRules
from app.services.alarm_templates import guidance_for, title_for
from app.utils.enums import AlarmSeverity, AlarmStatus


@dataclass(frozen=True)
class RuleAlarmCandidate:
    station_id: int
    target_type: str
    target_id: int
    alarm_type: str
    severity: AlarmSeverity
    moment: datetime


class AlarmEngine:
    def __init__(
        self,
        repository: AlarmRepository,
        rules: MonitoringRules = DEFAULT_MONITORING_RULES,
    ) -> None:
        self.repository, self.rules = repository, rules

    def evaluate(
        self,
        *,
        station_id: int,
        tanks: list[object],
        pumps: list[object],
        readings: list[object],
        moment: datetime,
        delivery_tank_ids: set[int] | None = None,
    ) -> list[object]:
        return self.raise_candidates(
            self.candidates(
                station_id=station_id, tanks=tanks, pumps=pumps, readings=readings,
                moment=moment, delivery_tank_ids=delivery_tank_ids,
            )
        )

    def candidates(
        self,
        *,
        station_id: int,
        tanks: list[object],
        pumps: list[object],
        readings: list[object],
        moment: datetime,
        delivery_tank_ids: set[int] | None = None,
    ) -> list[RuleAlarmCandidate]:
        """Return Stage 7 rule facts without creating a parallel alarm system."""

        delivery_tank_ids = delivery_tank_ids or set()
        candidates: list[RuleAlarmCandidate] = []
        tank_readings = {
            x.tank_id: x
            for x in readings
            if getattr(x, "pump_id", None) is None
            and getattr(x, "tank_id", None) is not None
        }
        pump_readings = {
            x.pump_id: x for x in readings if getattr(x, "pump_id", None) is not None
        }
        for tank in tanks:
            reading = tank_readings.get(tank.tank_id)
            if reading is None:
                continue
            if tank.water_level > self.rules.critical_water_level:
                candidates.append(RuleAlarmCandidate(station_id, "TANK", tank.tank_id, "HIGH_WATER_LEVEL", AlarmSeverity.HIGH, moment))
            if float(reading.data_quality_score) < self.rules.quality_minimum_score:
                candidates.append(RuleAlarmCandidate(station_id, "TANK", tank.tank_id, "LOW_DATA_QUALITY", AlarmSeverity.MEDIUM, moment))
            flags = set(reading.quality_flags_json)
            if "SENSOR_STUCK" in flags:
                candidates.append(RuleAlarmCandidate(station_id, "TANK", tank.tank_id, "SENSOR_STUCK", AlarmSeverity.HIGH, moment))
            if "TANK_SALES_MISMATCH" in flags:
                candidates.append(RuleAlarmCandidate(station_id, "TANK", tank.tank_id, "TANK_SALES_MISMATCH", AlarmSeverity.HIGH, moment))
            if "SENSOR_SPIKE" in flags and tank.tank_id not in delivery_tank_ids:
                candidates.append(RuleAlarmCandidate(station_id, "TANK", tank.tank_id, "SENSOR_SPIKE", AlarmSeverity.MEDIUM, moment))
        for pump in pumps:
            reading = pump_readings.get(pump.pump_id)
            if reading is None:
                continue
            if pump.motor_current > pump.maximum_motor_current:
                candidates.append(RuleAlarmCandidate(station_id, "PUMP", pump.pump_id, "HIGH_MOTOR_CURRENT", AlarmSeverity.HIGH, moment))
            if pump.pressure > pump.maximum_pressure:
                candidates.append(RuleAlarmCandidate(station_id, "PUMP", pump.pump_id, "HIGH_PRESSURE", AlarmSeverity.HIGH, moment))
            if pump.is_active_status and pump.flow_rate < pump.minimum_flow_rate:
                candidates.append(RuleAlarmCandidate(station_id, "PUMP", pump.pump_id, "LOW_FLOW", AlarmSeverity.HIGH, moment))
            if float(reading.data_quality_score) < self.rules.quality_minimum_score:
                candidates.append(RuleAlarmCandidate(station_id, "PUMP", pump.pump_id, "LOW_DATA_QUALITY", AlarmSeverity.MEDIUM, moment))
        return candidates

    def raise_candidates(
        self,
        candidates: list[RuleAlarmCandidate],
        ai_results: dict[tuple[str, int], object] | None = None,
    ) -> list[object]:
        created: list[object] = []
        ai_results = ai_results or {}
        for candidate in candidates:
            created += self._raise(
                candidate.station_id, candidate.target_type, candidate.target_id,
                candidate.alarm_type, candidate.severity, candidate.moment,
                ai_results.get((candidate.target_type, candidate.target_id)),
            )
        # Model-only HIGH/CRITICAL results also use the existing alarm repository and dedup key.
        candidate_targets = {(item.target_type, item.target_id) for item in candidates}
        for key, result in ai_results.items():
            if key in candidate_targets or not getattr(result, "is_anomaly", False):
                continue
            if getattr(result, "decision_source", "NONE") != "MODEL":
                continue
            created += self._raise(
                result.station_id, key[0], key[1], "AI_ANOMALY",
                AlarmSeverity(getattr(result, "severity", "MEDIUM")), result.timestamp, result,
            )
        return created

    def _raise(
        self,
        station_id: int,
        target_type: str,
        target_id: int,
        alarm_type: str,
        severity: AlarmSeverity,
        moment: datetime,
        ai_result: object | None = None,
    ) -> list[object]:
        if self.repository.active_for_key(
            station_id, target_type, target_id, alarm_type
        ):
            return []
        description, recommendation, probable_causes = guidance_for(alarm_type)
        if ai_result is not None:
            findings = tuple(getattr(ai_result, "findings", ()))
            if findings:
                description = f"{description} {' '.join(findings)}"
            checks = tuple(getattr(ai_result, "recommended_checks", ()))
            if checks:
                recommendation = " ".join(checks)
            causes = tuple(getattr(ai_result, "probable_causes", ()))
            if causes:
                probable_causes = [{"description": item} for item in causes]
        values = {
            "station_id": station_id,
            "tank_id": target_id if target_type == "TANK" else None,
            "pump_id": target_id if target_type == "PUMP" else None,
            "alarm_type": alarm_type,
            "severity": severity,
            "title": title_for(alarm_type),
            "description": description,
            "recommended_action": recommendation,
            "probable_causes": probable_causes,
            "status": AlarmStatus.NEW,
            "detected_at": moment,
            "anomaly_score": getattr(ai_result, "risk_score", None),
            "risk_level": getattr(ai_result, "risk_level", None),
            "decision_source": getattr(ai_result, "decision_source", None),
            "anomaly_type": getattr(ai_result, "anomaly_type", None),
            "model_version": getattr(ai_result, "model_version", None),
            "model_outlier": getattr(ai_result, "model_outlier", None),
            "triggered_rules_json": list(getattr(ai_result, "triggered_rules", ())),
            "findings_json": list(getattr(ai_result, "findings", ())),
            "recommended_checks_json": list(getattr(ai_result, "recommended_checks", ())),
            "data_quality_note": getattr(ai_result, "data_quality_note", None),
        }
        return [self.repository.create(values)]
