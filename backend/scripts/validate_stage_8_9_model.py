"""Read-only validation of the active model against baseline and flow-drop samples."""

from copy import copy
from datetime import timedelta

import pandas as pd
from sqlalchemy import select

from app.database import SessionLocal
from app.models.sensor_reading import SensorReading
from app.ml.feature_engineering import AnomalyFeatureEngineer
from app.ml.model_registry import AnomalyModelRegistry
from app.services.alarm_engine import RuleAlarmCandidate
from app.services.live_anomaly_service import LiveAnomalyService
from app.utils.enums import AlarmSeverity


def main() -> None:
    session = SessionLocal()
    try:
        latest = session.scalar(
            select(SensorReading)
            .where(
                SensorReading.pump_id == 4,
                SensorReading.simulation_run_id == 13,
                SensorReading.flow_rate > 0,
            )
            .order_by(SensorReading.reading_timestamp.desc())
            .limit(1)
        )
        if latest is None:
            raise RuntimeError("Pump 4 has no persisted active sensor history for validation.")

        baseline = copy(latest)
        baseline.reading_timestamp = latest.reading_timestamp + timedelta(minutes=1)
        baseline.sequence_number = (latest.sequence_number or 0) + 1
        baseline.flow_rate = latest.flow_rate
        baseline.motor_current = latest.motor_current

        flow_drop = copy(baseline)
        flow_drop.flow_rate = 4.0
        flow_drop.motor_current = 14.0
        flow_drop.reading_timestamp = baseline.reading_timestamp + timedelta(minutes=1)
        flow_drop.sequence_number += 1

        service = LiveAnomalyService(session)
        normal = service.evaluate([baseline], [])[0]
        rule = RuleAlarmCandidate(
            station_id=flow_drop.station_id, target_type="PUMP", target_id=4,
            alarm_type="LOW_FLOW", severity=AlarmSeverity.HIGH,
            moment=flow_drop.reading_timestamp,
        )
        anomaly = service.evaluate([flow_drop], [rule])[0]
        run_rows = list(
            session.scalars(
                select(SensorReading)
                .where(SensorReading.pump_id == 4, SensorReading.simulation_run_id == 13)
                .order_by(SensorReading.reading_timestamp)
            )
        )
        engineered = AnomalyFeatureEngineer().engineer(
            pd.DataFrame([service._reading_row(item) for item in run_rows])
        ).features["pump"]
        active_features = engineered[engineered["flow_rate"] > 0]
        active_risks = AnomalyModelRegistry(session).get_active("pump").risk_scorer.score_features(
            AnomalyModelRegistry(session).get_active("pump").model, active_features
        )
        high_count = sum(item.risk_level.value in {"HIGH", "CRITICAL"} for item in active_risks)
        print(
            "baseline "
            f"flow={float(baseline.flow_rate):.3f} current={float(baseline.motor_current):.3f} "
            f"state={normal.ai_state.value} risk={normal.risk_score} level={normal.risk_level} decision={normal.decision_source}"
        )
        print(
            "normal_active_diagnostic "
            f"samples={len(active_risks)} average_risk={sum(item.risk_score for item in active_risks) / len(active_risks):.3f} "
            f"high_or_critical={high_count} false_positive_rate={100 * high_count / len(active_risks):.3f}%"
        )
        print(
            "flow_drop "
            f"flow={float(flow_drop.flow_rate):.3f} current={float(flow_drop.motor_current):.3f} "
            f"state={anomaly.ai_state.value} decision_function={anomaly.decision_function} risk={anomaly.risk_score} "
            f"level={anomaly.risk_level} decision={anomaly.decision_source} "
            f"severity={anomaly.severity} model={anomaly.model_version}"
        )
    finally:
        session.rollback()
        session.close()


if __name__ == "__main__":
    main()
