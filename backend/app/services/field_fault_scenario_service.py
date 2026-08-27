"""Apply bounded field-device scenario effects through existing topology and alarms."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.communication_port import CommunicationPort
from app.models.device_controller import DeviceController
from app.models.pump import Pump
from app.models.tank_probe import TankProbe
from app.repositories.alarm_repository import AlarmRepository
from app.services.alarm_engine import AlarmEngine, RuleAlarmCandidate
from app.utils.enums import (
    AlarmSeverity,
    ControllerStatus,
    PortStatus,
    ProbeStatus,
    PumpStatus,
    ScenarioType,
)


class FieldFaultScenarioService:
    """Persist scenario-owned device states without modifying topology links."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.alarms = AlarmEngine(AlarmRepository(db))
        self._previous_states: dict[tuple[object, ...], list[tuple[object, object]]] = {}

    def apply(self, scenarios: list[dict[str, object]], moment: datetime) -> list[object]:
        """Apply active faults and restore only scenarios that are no longer active."""

        created: list[object] = []
        active_keys = {self._key(item) for item in scenarios}
        self._recover_inactive(active_keys, moment)
        for scenario in scenarios:
            kind = str(scenario["scenario_type"])
            target_id = int(scenario["target_id"])
            key = self._key(scenario)
            if kind == ScenarioType.PORT_COMMUNICATION_ERROR.value:
                port = self.db.get(CommunicationPort, target_id)
                if port is None:
                    continue
                self._remember(key, [(port, port.status)])
                port.status = PortStatus.OFFLINE
                created += self._alarm(port.controller.station_id, "PORT", port.id, kind, moment)
            elif kind == ScenarioType.USC_INITIALIZATION_ERROR.value:
                controller = self.db.get(DeviceController, target_id)
                if controller is None:
                    continue
                ports = list(self.db.scalars(select(CommunicationPort).where(CommunicationPort.controller_id == controller.id)))
                self._remember(key, [(controller, controller.status), *[(port, port.status) for port in ports]])
                controller.status = ControllerStatus.ERROR
                for port in ports:
                    port.status = PortStatus.OFFLINE
                created += self._alarm(controller.station_id, "CONTROLLER", controller.id, kind, moment)
            elif kind == ScenarioType.PROBE_COMMUNICATION_ERROR.value:
                probe = self.db.get(TankProbe, target_id)
                if probe is None:
                    continue
                self._remember(key, [(probe, probe.status)])
                probe.status = ProbeStatus.OFFLINE
                created += self._alarm(probe.tank.station_id, "PROBE", probe.id, kind, moment)
            elif kind == ScenarioType.PUMP_NOT_CONNECTED.value:
                pump = self.db.get(Pump, target_id)
                if pump is None:
                    continue
                self._remember(key, [(pump, pump.status)])
                pump.status = PumpStatus.OFFLINE
                created += self._alarm(pump.station_id, "PUMP", pump.id, kind, moment)
        return created

    @staticmethod
    def _key(scenario: dict[str, object]) -> tuple[object, ...]:
        return (
            scenario.get("id"),
            scenario["scenario_type"],
            scenario["target_id"],
        )

    def _remember(
        self, key: tuple[object, ...], states: list[tuple[object, object]]
    ) -> None:
        self._previous_states.setdefault(key, states)

    def _recover_inactive(
        self, active_keys: set[tuple[object, ...]], moment: datetime
    ) -> None:
        for key in tuple(self._previous_states):
            if key in active_keys:
                continue
            for device, previous_status in self._previous_states.pop(key):
                setattr(device, "status", previous_status)
                if hasattr(device, "last_communication_at"):
                    setattr(device, "last_communication_at", moment)

    def _alarm(
        self, station_id: int, target_type: str, target_id: int, alarm_type: str, moment: datetime
    ) -> list[object]:
        return self.alarms.raise_candidates([
            RuleAlarmCandidate(station_id, target_type, target_id, alarm_type, AlarmSeverity.HIGH, moment)
        ])
