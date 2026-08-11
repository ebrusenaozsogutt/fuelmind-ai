"""Rule alarm evaluation and active-alarm deduplication."""

from datetime import datetime
from app.repositories.alarm_repository import AlarmRepository
from app.services.monitoring_rules import DEFAULT_MONITORING_RULES, MonitoringRules
from app.services.alarm_templates import guidance_for
from app.utils.enums import AlarmSeverity, AlarmStatus


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
        delivery_tank_ids = delivery_tank_ids or set()
        created = []
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
                created += self._raise(
                    station_id,
                    "TANK",
                    tank.tank_id,
                    "HIGH_WATER_LEVEL",
                    AlarmSeverity.HIGH,
                    moment,
                )
            if float(reading.data_quality_score) < self.rules.quality_minimum_score:
                created += self._raise(
                    station_id,
                    "TANK",
                    tank.tank_id,
                    "LOW_DATA_QUALITY",
                    AlarmSeverity.MEDIUM,
                    moment,
                )
            flags = set(reading.quality_flags_json)
            if "SENSOR_STUCK" in flags:
                created += self._raise(
                    station_id,
                    "TANK",
                    tank.tank_id,
                    "SENSOR_STUCK",
                    AlarmSeverity.HIGH,
                    moment,
                )
            if "TANK_SALES_MISMATCH" in flags:
                created += self._raise(
                    station_id,
                    "TANK",
                    tank.tank_id,
                    "TANK_SALES_MISMATCH",
                    AlarmSeverity.HIGH,
                    moment,
                )
            if "SENSOR_SPIKE" in flags and tank.tank_id not in delivery_tank_ids:
                created += self._raise(
                    station_id,
                    "TANK",
                    tank.tank_id,
                    "SENSOR_SPIKE",
                    AlarmSeverity.MEDIUM,
                    moment,
                )
        for pump in pumps:
            reading = pump_readings.get(pump.pump_id)
            if reading is None:
                continue
            if pump.motor_current > pump.maximum_motor_current:
                created += self._raise(
                    station_id,
                    "PUMP",
                    pump.pump_id,
                    "HIGH_MOTOR_CURRENT",
                    AlarmSeverity.HIGH,
                    moment,
                )
            if pump.pressure > pump.maximum_pressure:
                created += self._raise(
                    station_id,
                    "PUMP",
                    pump.pump_id,
                    "HIGH_PRESSURE",
                    AlarmSeverity.HIGH,
                    moment,
                )
            if pump.is_active_status and pump.flow_rate < pump.minimum_flow_rate:
                created += self._raise(
                    station_id,
                    "PUMP",
                    pump.pump_id,
                    "LOW_FLOW",
                    AlarmSeverity.HIGH,
                    moment,
                )
            if float(reading.data_quality_score) < self.rules.quality_minimum_score:
                created += self._raise(
                    station_id,
                    "PUMP",
                    pump.pump_id,
                    "LOW_DATA_QUALITY",
                    AlarmSeverity.MEDIUM,
                    moment,
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
    ) -> list[object]:
        if self.repository.active_for_key(
            station_id, target_type, target_id, alarm_type
        ):
            return []
        description, recommendation, probable_causes = guidance_for(alarm_type)
        values = {
            "station_id": station_id,
            "tank_id": target_id if target_type == "TANK" else None,
            "pump_id": target_id if target_type == "PUMP" else None,
            "alarm_type": alarm_type,
            "severity": severity,
            "title": alarm_type.replace("_", " ").title(),
            "description": description,
            "recommended_action": recommendation,
            "probable_causes": probable_causes,
            "status": AlarmStatus.NEW,
            "detected_at": moment,
            "anomaly_score": None,
        }
        return [self.repository.create(values)]
