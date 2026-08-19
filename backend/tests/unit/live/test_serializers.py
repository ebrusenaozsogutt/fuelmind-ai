"""Tests for the pure live tick message serializer."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.live.serializers import serialize_simulation_tick
from app.services.live_topology_service import (
    CommunicationPortLiveState,
    ControllerLiveState,
    LiveTopologySnapshot,
    NozzleLiveState,
    ProbeLiveState,
)
from app.simulation.field_device import ProbeObservation
from app.live.serializers import serialize_alarm_created
from app.utils.enums import (
    AlarmSeverity,
    AlarmStatus,
    ControllerStatus,
    ControllerType,
    NozzleStatus,
    PortStatus,
    PortType,
    ProbeStatus,
)
from app.simulation.state import ActiveSaleState, PumpState, TankState
from app.simulation.tick_result import SimulationTickEvent, SimulationTickResult
from app.utils.enums import PumpStatus


def test_serializes_complete_tick_as_deterministic_json_without_mutation() -> None:
    moment = datetime(2026, 8, 6, 11, 30, 5, tzinfo=timezone.utc)
    tank = TankState(1, 1, 2, "T-1", 1_000, 700, 699, 100, 50, 23, 1, "ACTIVE")
    pump = PumpState(3, 1, 1, 2, "P-3", PumpStatus.ACTIVE, 42, 10, 20, 8, 20, 3, 4, 35, 12, 1)
    sale = ActiveSaleState("SALE-1", 1, 1, 3, 2, moment, 20, 20, 45, moment)
    result = SimulationTickResult(
        1, moment, 42, [tank], [pump], completed_sales=[sale],
        events=[SimulationTickEvent("SALE_COMPLETED", 1, moment, "PUMP", 3, {"status": PumpStatus.ACTIVE})],
    )

    payload = serialize_simulation_tick(15, result, generated_at=moment)

    assert set(payload) == {
        "event_type", "simulation_run_id", "station_id", "simulation_time",
        "sequence", "tanks", "pumps", "sales", "events", "active_scenarios",
        "generated_at", "controllers", "ports", "probes", "nozzles",
    }
    assert payload["event_type"] == "simulation_tick"
    assert payload["simulation_run_id"] == 15
    assert payload["sequence"] == 42
    assert payload["simulation_time"] == moment.isoformat()
    assert payload["generated_at"] == moment.isoformat()
    assert payload["tanks"][0]["true_level_liters"] == 700
    assert payload["pumps"][0]["status"] == "ACTIVE"
    assert payload["sales"][0]["completed_at"] == moment.isoformat()
    assert payload["events"][0]["payload"] == {"status": "ACTIVE"}
    assert payload["active_scenarios"] == []
    assert payload["controllers"] == payload["ports"] == payload["probes"] == []
    assert payload["nozzles"] == []
    assert result.sequence_number == 42 and tank.true_level_liters == 700
    json.dumps(payload)


def test_serializes_empty_optional_collections() -> None:
    moment = datetime(2026, 8, 6, tzinfo=timezone.utc)
    result = SimulationTickResult(1, moment, 1)

    payload = serialize_simulation_tick(1, result, generated_at=moment)

    assert payload["tanks"] == []
    assert payload["pumps"] == []
    assert payload["sales"] == []
    assert payload["events"] == []
    assert payload["active_scenarios"] == []


def test_serializes_additive_field_topology_from_the_same_tick() -> None:
    moment = datetime(2026, 8, 6, tzinfo=timezone.utc)
    observation = ProbeObservation(
        probe_id=9,
        tank_id=1,
        fuel_height_mm=1_300,
        fuel_volume_liters=650,
        water_height_mm=10,
        water_volume_liters=5,
        temperature_celsius=18.7,
        data_quality_score=97,
        quality_flags=("SENSOR_STUCK",),
    )
    result = SimulationTickResult(
        1,
        moment,
        7,
        pump_results=[PumpState(3, 1, 1, 2, "P-3", PumpStatus.ACTIVE, 42, 10, 20, 8)],
        probe_observations=[observation],
    )
    topology = LiveTopologySnapshot(
        controllers=[
            ControllerLiveState(1, 1, "CTRL-1", "Controller", ControllerType.GENERIC, ControllerStatus.ONLINE, True, None)
        ],
        ports=[
            CommunicationPortLiveState(2, 1, 1, "Pump bus", PortType.PUMP, "RS-485", 9600, PortStatus.ONLINE, True, None)
        ],
        probes=[ProbeLiveState(9, 1, 2, "PRB-1", "Probe", ProbeStatus.ONLINE, True, None)],
        nozzles=[
            NozzleLiveState(11, 3, 2, "NZL-1", 1, NozzleStatus.AVAILABLE, 125_342.9, True, "DSL", "Diesel")
        ],
        pump_port_ids={3: 2},
        dispensing_nozzle_ids=frozenset({11}),
    )

    payload = serialize_simulation_tick(15, result, generated_at=moment, topology=topology)

    assert payload["pumps"][0]["communication_port_id"] == 2
    assert payload["controllers"][0]["status"] == "ONLINE"
    assert payload["ports"][0]["controller_id"] == 1
    assert payload["probes"][0] == {
        "id": 9, "tank_id": 1, "communication_port_id": 2,
        "code": "PRB-1", "name": "Probe", "status": "ONLINE", "is_active": True,
        "last_communication_at": None, "fuel_height_mm": 1_300,
        "fuel_volume_liters": 650, "water_height_mm": 10,
        "water_volume_liters": 5, "temperature_celsius": 18.7,
        "data_quality_score": 97, "quality_flags": ["SENSOR_STUCK"],
        "reading_timestamp": None,
    }
    assert payload["nozzles"][0]["totalizer_liters"] == 125_342.9
    assert payload["nozzles"][0]["status"] == "DISPENSING"


def test_serializes_alarm_created_contract() -> None:
    alarm = SimpleNamespace(
        id=8, station_id=2, tank_id=3, pump_id=None, alarm_type="LOW_FLOW",
        severity=AlarmSeverity.HIGH, title="Low flow", description="Pump flow is low",
        anomaly_type=None, status=AlarmStatus.NEW,
        recommended_action="Check the pump", probable_causes=[{"description": "Filter"}],
        detected_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
    )
    payload = serialize_alarm_created(alarm)
    assert payload["event_type"] == "alarm_created"
    assert payload["alarm_id"] == 8 and payload["station_id"] == 2
    assert payload["severity"] == "HIGH" and payload["status"] == "NEW"
    assert payload["recommended_action"] == "Check the pump"
    assert payload["probable_causes"] == [{"description": "Filter"}]
