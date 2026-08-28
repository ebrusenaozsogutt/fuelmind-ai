"""Compact station topology snapshots for live REST and WebSocket consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.models.communication_port import CommunicationPort
from app.models.device_controller import DeviceController
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.probe_reading import ProbeReading
from app.models.pump import Pump
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.utils.enums import NozzleStatus


@dataclass(frozen=True)
class ControllerLiveState:
    id: int
    station_id: int
    code: str
    name: str
    controller_type: object
    status: object
    is_active: bool
    last_communication_at: datetime | None


@dataclass(frozen=True)
class CommunicationPortLiveState:
    id: int
    controller_id: int
    port_number: int
    name: str
    port_type: object
    protocol: str | None
    baud_rate: int | None
    status: object
    is_active: bool
    last_communication_at: datetime | None


@dataclass(frozen=True)
class ProbeLiveState:
    id: int
    tank_id: int
    communication_port_id: int | None
    code: str
    name: str
    status: object
    is_active: bool
    last_communication_at: datetime | None
    latest_reading: ProbeReading | None = None


@dataclass(frozen=True)
class NozzleLiveState:
    id: int
    pump_id: int
    fuel_type_id: int
    code: str
    nozzle_number: int
    status: object
    totalizer_liters: object
    is_active: bool
    fuel_type_code: str
    fuel_type_name: str


@dataclass(frozen=True)
class LiveTopologySnapshot:
    """Flat, relational live topology without configuration-heavy fields."""

    controllers: list[ControllerLiveState] = field(default_factory=list)
    ports: list[CommunicationPortLiveState] = field(default_factory=list)
    probes: list[ProbeLiveState] = field(default_factory=list)
    nozzles: list[NozzleLiveState] = field(default_factory=list)
    pump_port_ids: dict[int, int | None] = field(default_factory=dict)
    dispensing_nozzle_ids: frozenset[int] = field(default_factory=frozenset)

    def effective_nozzle_status(self, nozzle: NozzleLiveState) -> object:
        """Expose in-memory dispensing without rewriting persistent availability."""

        if nozzle.id in self.dispensing_nozzle_ids:
            return NozzleStatus.DISPENSING
        return nozzle.status


class LiveTopologyService:
    """Load topology in bounded station-wide queries, never one query per device."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._tables = inspect(db.get_bind())

    def snapshot(
        self,
        station_id: int,
        *,
        dispensing_nozzle_ids: set[int] | frozenset[int] = frozenset(),
        include_latest_probe_readings: bool = False,
        simulation_run_id: int | None = None,
    ) -> LiveTopologySnapshot:
        """Return a current flat snapshot; absent Stage 9 tables mean empty lists."""

        controllers = self._controllers(station_id)
        ports = self._ports(station_id)
        latest_readings = (
            self._latest_probe_readings(station_id, simulation_run_id=simulation_run_id)
            if include_latest_probe_readings
            else {}
        )
        probes = self._probes(station_id, latest_readings)
        nozzles = self._nozzles(station_id)
        return LiveTopologySnapshot(
            controllers=controllers,
            ports=ports,
            probes=probes,
            nozzles=nozzles,
            pump_port_ids=self._pump_port_ids(station_id),
            dispensing_nozzle_ids=frozenset(dispensing_nozzle_ids),
        )

    def _controllers(self, station_id: int) -> list[ControllerLiveState]:
        if not self._tables.has_table(DeviceController.__tablename__):
            return []
        return [
            ControllerLiveState(
                id=item.id,
                station_id=item.station_id,
                code=item.code,
                name=item.name,
                controller_type=item.controller_type,
                status=item.status,
                is_active=item.is_active,
                last_communication_at=item.last_communication_at,
            )
            for item in self.db.scalars(
                select(DeviceController)
                .where(DeviceController.station_id == station_id)
                .order_by(DeviceController.id)
            )
        ]

    def _ports(self, station_id: int) -> list[CommunicationPortLiveState]:
        if not {
            DeviceController.__tablename__,
            CommunicationPort.__tablename__,
        } <= set(self._tables.get_table_names()):
            return []
        return [
            CommunicationPortLiveState(
                id=item.id,
                controller_id=item.controller_id,
                port_number=item.port_number,
                name=item.name,
                port_type=item.port_type,
                protocol=item.protocol,
                baud_rate=item.baud_rate,
                status=item.status,
                is_active=item.is_active,
                last_communication_at=item.last_communication_at,
            )
            for item in self.db.scalars(
                select(CommunicationPort)
                .join(DeviceController)
                .where(DeviceController.station_id == station_id)
                .order_by(CommunicationPort.id)
            )
        ]

    def _probes(
        self, station_id: int, latest_readings: dict[int, ProbeReading]
    ) -> list[ProbeLiveState]:
        if not {Tank.__tablename__, TankProbe.__tablename__} <= set(
            self._tables.get_table_names()
        ):
            return []
        return [
            ProbeLiveState(
                id=item.id,
                tank_id=item.tank_id,
                communication_port_id=item.communication_port_id,
                code=item.code,
                name=item.name,
                status=item.status,
                is_active=item.is_active,
                last_communication_at=item.last_communication_at,
                latest_reading=latest_readings.get(item.id),
            )
            for item in self.db.scalars(
                select(TankProbe)
                .join(Tank)
                .where(Tank.station_id == station_id)
                .order_by(TankProbe.id)
            )
        ]

    def _nozzles(self, station_id: int) -> list[NozzleLiveState]:
        if not {Pump.__tablename__, Nozzle.__tablename__, FuelType.__tablename__} <= set(
            self._tables.get_table_names()
        ):
            return []
        rows = self.db.execute(
            select(Nozzle, FuelType.code, FuelType.name)
            .join(Pump, Nozzle.pump_id == Pump.id)
            .join(FuelType, Nozzle.fuel_type_id == FuelType.id)
            .where(Pump.station_id == station_id)
            .order_by(Nozzle.id)
        )
        return [
            NozzleLiveState(
                id=nozzle.id,
                pump_id=nozzle.pump_id,
                fuel_type_id=nozzle.fuel_type_id,
                code=nozzle.code,
                nozzle_number=nozzle.nozzle_number,
                status=nozzle.status,
                totalizer_liters=nozzle.totalizer_liters,
                is_active=nozzle.is_active,
                fuel_type_code=fuel_code,
                fuel_type_name=fuel_name,
            )
            for nozzle, fuel_code, fuel_name in rows
        ]

    def _pump_port_ids(self, station_id: int) -> dict[int, int | None]:
        if not self._tables.has_table(Pump.__tablename__):
            return {}
        return dict(
            self.db.execute(
                select(Pump.id, Pump.communication_port_id).where(
                    Pump.station_id == station_id
                )
            ).all()
        )

    def _latest_probe_readings(
        self, station_id: int, *, simulation_run_id: int | None = None
    ) -> dict[int, ProbeReading]:
        if not {Tank.__tablename__, TankProbe.__tablename__, ProbeReading.__tablename__} <= set(
            self._tables.get_table_names()
        ):
            return {}
        ranked_query = (
            select(
                ProbeReading.id.label("reading_id"),
                func.row_number()
                .over(
                    partition_by=ProbeReading.probe_id,
                    order_by=(
                        ProbeReading.reading_timestamp.desc(),
                        ProbeReading.id.desc(),
                    ),
                )
                .label("rank"),
            )
            .join(Tank, ProbeReading.tank_id == Tank.id)
            .where(Tank.station_id == station_id)
        )
        if simulation_run_id is not None:
            ranked_query = ranked_query.where(
                ProbeReading.simulation_run_id == simulation_run_id
            )
        ranked = ranked_query.subquery()
        readings = self.db.scalars(
            select(ProbeReading).where(
                ProbeReading.id.in_(
                    select(ranked.c.reading_id).where(ranked.c.rank == 1)
                )
            )
        )
        return {reading.probe_id: reading for reading in readings}


def live_topology_payload(
    snapshot: LiveTopologySnapshot,
    *,
    probe_measurements: dict[int, object] | None = None,
) -> dict[str, list[dict[str, object]]]:
    """Convert a topology snapshot to stable JSON-ready flat DTO dictionaries."""

    measurements = probe_measurements or {}
    return {
        "controllers": [
            {
                "id": item.id,
                "station_id": item.station_id,
                "code": item.code,
                "name": item.name,
                "controller_type": _enum_value(item.controller_type),
                "status": _enum_value(item.status),
                "is_active": item.is_active,
                "last_communication_at": item.last_communication_at,
            }
            for item in snapshot.controllers
        ],
        "ports": [
            {
                "id": item.id,
                "controller_id": item.controller_id,
                "port_number": item.port_number,
                "name": item.name,
                "port_type": _enum_value(item.port_type),
                "protocol": item.protocol,
                "baud_rate": item.baud_rate,
                "status": _enum_value(item.status),
                "is_active": item.is_active,
                "last_communication_at": item.last_communication_at,
            }
            for item in snapshot.ports
        ],
        "probes": [
            _probe_payload(item, measurements.get(item.id, item.latest_reading))
            for item in snapshot.probes
        ],
        "nozzles": [
            {
                "id": item.id,
                "pump_id": item.pump_id,
                "fuel_type_id": item.fuel_type_id,
                "code": item.code,
                "nozzle_number": item.nozzle_number,
                "status": _enum_value(snapshot.effective_nozzle_status(item)),
                "totalizer_liters": item.totalizer_liters,
                "is_active": item.is_active,
                "fuel_type_code": item.fuel_type_code,
                "fuel_type_name": item.fuel_type_name,
            }
            for item in snapshot.nozzles
        ],
    }


def _probe_payload(item: ProbeLiveState, measurement: object | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": item.id,
        "tank_id": item.tank_id,
        "communication_port_id": item.communication_port_id,
        "code": item.code,
        "name": item.name,
        "status": _enum_value(item.status),
        "is_active": item.is_active,
        "last_communication_at": item.last_communication_at,
        "fuel_height_mm": None,
        "fuel_volume_liters": None,
        "water_height_mm": None,
        "water_volume_liters": None,
        "temperature_celsius": None,
        "data_quality_score": None,
        "quality_flags": [],
        "reading_timestamp": None,
    }
    if measurement is None:
        return payload
    payload.update(
        fuel_height_mm=getattr(measurement, "fuel_height_mm"),
        fuel_volume_liters=getattr(measurement, "fuel_volume_liters"),
        water_height_mm=getattr(measurement, "water_height_mm"),
        water_volume_liters=getattr(measurement, "water_volume_liters"),
        temperature_celsius=getattr(measurement, "temperature_celsius"),
        data_quality_score=getattr(measurement, "data_quality_score", None),
        quality_flags=list(
            getattr(
                measurement,
                "quality_flags",
                getattr(measurement, "quality_flags_json", []),
            )
        ),
        reading_timestamp=getattr(measurement, "reading_timestamp", None),
    )
    return payload


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)
