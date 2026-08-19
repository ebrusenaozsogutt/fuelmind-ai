"""Stable JSON payloads for live simulation messages."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.services.live_topology_service import (
    LiveTopologySnapshot,
    live_topology_payload,
)
from app.simulation.tick_result import SimulationTickResult
from app.utils.datetime_utils import utc_now


def serialize_alarm_created(alarm: object) -> dict[str, Any]:
    """Public alarm-created message shared by desktop and web clients."""
    return {
        "event_type": "alarm_created", "alarm_id": alarm.id,
        "station_id": alarm.station_id, "tank_id": alarm.tank_id,
        "pump_id": alarm.pump_id, "alarm_type": alarm.alarm_type,
        "severity": alarm.severity.value, "title": alarm.title,
        "description": alarm.description,
        "anomaly_type": getattr(alarm, "anomaly_type", None),
        "recommended_action": getattr(alarm, "recommended_action", None),
        "probable_causes": _json_value(getattr(alarm, "probable_causes", None)),
        "anomaly_score": _json_value(getattr(alarm, "anomaly_score", None)),
        "risk_level": getattr(alarm, "risk_level", None),
        "decision_source": getattr(alarm, "decision_source", None),
        "model_version": getattr(alarm, "model_version", None),
        "model_outlier": getattr(alarm, "model_outlier", None),
        "triggered_rules": _json_value(getattr(alarm, "triggered_rules_json", None)),
        "findings": _json_value(getattr(alarm, "findings_json", None)),
        "recommended_checks": _json_value(getattr(alarm, "recommended_checks_json", None)),
        "data_quality_note": getattr(alarm, "data_quality_note", None),
        "status": alarm.status.value, "detected_at": alarm.detected_at.isoformat(),
    }


def serialize_simulation_tick(
    simulation_run_id: int,
    tick_result: SimulationTickResult,
    *,
    generated_at: datetime | None = None,
    topology: LiveTopologySnapshot | None = None,
) -> dict[str, Any]:
    """Convert one completed tick into the public WebSocket message contract."""

    timestamp = generated_at or utc_now()
    topology = topology or LiveTopologySnapshot()
    topology_payload = {
        key: _json_value(value)
        for key, value in live_topology_payload(
            topology,
            probe_measurements={
                observation.probe_id: observation
                for observation in tick_result.probe_observations
            },
        ).items()
    }
    return {
        "event_type": "simulation_tick",
        "simulation_run_id": simulation_run_id,
        "station_id": tick_result.station_id,
        "simulation_time": tick_result.simulation_time.isoformat(),
        "sequence": tick_result.sequence_number,
        "tanks": [
            {
                "tank_id": tank.tank_id,
                "fuel_type_id": tank.fuel_type_id,
                "code": tank.code,
                "true_level_liters": tank.true_level_liters,
                "measured_level_liters": tank.measured_level_liters,
                "capacity_liters": tank.capacity_liters,
                "temperature": tank.temperature,
                "water_level": tank.water_level,
            }
            for tank in tick_result.tank_results
        ],
        "pumps": [
            {
                "pump_id": pump.pump_id,
                "tank_id": pump.tank_id,
                "status": pump.status.value,
                "flow_rate": pump.flow_rate,
                "pressure": pump.pressure,
                "motor_current": pump.motor_current,
                "temperature": pump.temperature,
                "error_count": pump.error_count,
                "working_duration": pump.total_working_hours,
                "communication_port_id": topology.pump_port_ids.get(pump.pump_id),
            }
            for pump in tick_result.pump_results
        ],
        "sales": [
            {
                "sale_id": sale.sale_id,
                "pump_id": sale.pump_id,
                "tank_id": sale.tank_id,
                "fuel_type_id": sale.fuel_type_id,
                "quantity_liters": sale.dispensed_quantity_liters,
                "started_at": sale.started_at.isoformat(),
                "completed_at": sale.last_updated_at.isoformat(),
                "nozzle_id": sale.nozzle_id,
                "attendant_id": sale.attendant_id,
                "attendant_name": sale.attendant_name,
                "shift_id": sale.shift_id,
                "shift_name": sale.shift_name,
            }
            for sale in tick_result.completed_sales
        ],
        "events": [
            {
                "event_type": event.event_type,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "event_timestamp": event.event_timestamp.isoformat(),
                "payload": _json_value(event.payload),
            }
            for event in tick_result.events
        ],
        "active_scenarios": tick_result.active_scenarios,
        "generated_at": timestamp.isoformat(),
        **topology_payload,
    }


def serialize_anomaly_evaluation(
    simulation_run_id: int,
    tick_result: SimulationTickResult,
) -> dict[str, Any]:
    """Publish AI as an additive event so the established tick contract stays unchanged."""

    return {
        "event_type": "anomaly_evaluation",
        "simulation_run_id": simulation_run_id,
        "station_id": tick_result.station_id,
        "simulation_time": tick_result.simulation_time.isoformat(),
        "sequence": tick_result.sequence_number,
        "results": [result.to_dict() for result in tick_result.ai_results],
    }


def _json_value(value: object) -> object:
    """Convert event payload values to JSON primitives without exposing internals."""

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return value
