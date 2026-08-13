"""Create one real-model flow-drop alarm and verify its REST detail contract.

This acceptance diagnostic uses persisted history and the active registry artifact.
It does not invent a risk score or write a synthetic sensor reading; only the alarm
created through the production AlarmEngine is committed.
"""

from copy import copy
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import require_operator_or_admin
from app.database import SessionLocal
from app.main import app
from app.models.alarm import Alarm
from app.models.sensor_reading import SensorReading
from app.repositories.alarm_repository import AlarmRepository
from app.services.alarm_engine import AlarmEngine, RuleAlarmCandidate
from app.services.live_anomaly_service import LiveAnomalyService
from app.utils.enums import AlarmSeverity, AlarmStatus


def main() -> None:
    session = SessionLocal()
    try:
        target = _available_target(session)
        if target is None:
            raise RuntimeError("No run-13 pump is available without an active LOW_FLOW alarm.")

        current = copy(target)
        current.reading_timestamp = target.reading_timestamp + timedelta(minutes=1)
        current.sequence_number = (target.sequence_number or 0) + 1
        current.flow_rate = 4.0
        current.motor_current = 14.0
        rule = RuleAlarmCandidate(
            station_id=current.station_id,
            target_type="PUMP",
            target_id=current.pump_id,
            alarm_type="LOW_FLOW",
            severity=AlarmSeverity.HIGH,
            moment=current.reading_timestamp,
        )
        result = LiveAnomalyService(session).evaluate([current], [rule])[0]
        created = AlarmEngine(AlarmRepository(session)).raise_candidates(
            [rule], {("PUMP", current.pump_id): result}
        )
        if len(created) != 1:
            raise RuntimeError("AlarmEngine did not create exactly one acceptance alarm.")

        alarm = created[0]
        session.commit()
        session.refresh(alarm)
        alarm_id = alarm.id
        expected = result.to_dict()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    app.dependency_overrides[require_operator_or_admin] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/alarms/{alarm_id}")
            response.raise_for_status()
            detail = response.json()
    finally:
        app.dependency_overrides.pop(require_operator_or_admin, None)

    print(
        "inference "
        f"risk={expected['risk_score']} level={expected['risk_level']} "
        f"decision={expected['decision_source']} model={expected['model_version']} "
        f"anomaly_type={expected['anomaly_type']}"
    )
    print(f"findings={expected['findings']}")
    print(f"causes={expected['probable_causes']}")
    print(f"checks={expected['recommended_checks']}")
    print(
        "alarm_detail "
        f"id={detail['id']} risk={detail['anomaly_score']} "
        f"level={detail['risk_level']} decision={detail['decision_source']} "
        f"model={detail['model_version']} anomaly_type={detail['anomaly_type']} "
        f"model_outlier={detail['model_outlier']} rules={detail['triggered_rules_json']}"
    )
    print(f"detail_findings={detail['findings_json']}")
    print(f"detail_causes={detail['probable_causes']}")
    print(f"detail_checks={detail['recommended_checks_json']}")


def _available_target(session) -> SensorReading | None:
    pump_ids = list(
        session.scalars(
            select(SensorReading.pump_id)
            .where(
                SensorReading.simulation_run_id == 13,
                SensorReading.pump_id.is_not(None),
                SensorReading.flow_rate > 0,
            )
            .distinct()
            .order_by(SensorReading.pump_id)
        )
    )
    active_statuses = (
        AlarmStatus.NEW,
        AlarmStatus.ACKNOWLEDGED,
        AlarmStatus.INVESTIGATING,
    )
    for pump_id in pump_ids:
        active = session.scalar(
            select(Alarm.id).where(
                Alarm.pump_id == pump_id,
                Alarm.alarm_type == "LOW_FLOW",
                Alarm.status.in_(active_statuses),
            )
        )
        if active is not None:
            continue
        reading = session.scalar(
            select(SensorReading)
            .where(
                SensorReading.simulation_run_id == 13,
                SensorReading.pump_id == pump_id,
                SensorReading.flow_rate > 0,
            )
            .order_by(SensorReading.reading_timestamp.desc())
            .limit(1)
        )
        if reading is not None:
            return reading
    return None


if __name__ == "__main__":
    main()
