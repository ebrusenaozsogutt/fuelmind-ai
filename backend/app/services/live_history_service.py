"""Read-only service for reconnect history and persisted live snapshots."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.repositories.pump_repository import PumpRepository
from app.repositories.sensor_reading_repository import SensorReadingRepository
from app.repositories.station_repository import StationRepository
from app.repositories.tank_repository import TankRepository
from app.schemas.live_data import SensorHistoryRead
from app.services.live_topology_service import LiveTopologyService, live_topology_payload
from app.utils.datetime_utils import utc_now


class LiveHistoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.readings = SensorReadingRepository(db)

    def station_history(self, station_id: int, **filters: object):
        self._station(station_id)
        return self.readings.history(station_id=station_id, **filters)  # type: ignore[arg-type]

    def tank_history(self, tank_id: int, **filters: object):
        if TankRepository(self.db).get(tank_id) is None:
            raise NotFoundError("Tank not found.")
        return self.readings.history(tank_id=tank_id, **filters)  # type: ignore[arg-type]

    def pump_history(self, pump_id: int, **filters: object):
        if PumpRepository(self.db).get(pump_id) is None:
            raise NotFoundError("Pump not found.")
        return self.readings.history(pump_id=pump_id, **filters)  # type: ignore[arg-type]

    def status(self, station_id: int, *, simulation_run_id: int | None = None):
        """Return a station snapshot scoped to the manager-owned live run.

        Sensor history deliberately remains cross-run for reporting and
        investigation.  A live dashboard, however, must never combine the
        sequence 1 of a new run with the final readings of an older run.
        """
        self._station(station_id)
        items = self.readings.history(
            station_id=station_id,
            simulation_run_id=simulation_run_id,
            from_time=datetime.min.replace(tzinfo=utc_now().tzinfo),
            to_time=utc_now(),
            limit=5000,
        )
        tanks = {item.tank_id: item for item in items if item.tank_id is not None}
        pumps = {item.pump_id: item for item in items if item.pump_id is not None}
        latest = items[-1] if items else None
        topology = LiveTopologyService(self.db).snapshot(
            station_id,
            include_latest_probe_readings=True,
            simulation_run_id=simulation_run_id,
        )
        return {
            "station_id": station_id,
            "latest_sequence": latest.sequence_number if latest else None,
            "latest_reading_time": latest.reading_timestamp if latest else None,
            "tanks": list(tanks.values()),
            "pumps": [
                self._pump_reading(item, topology.pump_port_ids.get(item.pump_id))
                for item in pumps.values()
            ],
            **live_topology_payload(topology),
        }

    @staticmethod
    def _pump_reading(item: object, communication_port_id: int | None) -> dict[str, object]:
        """Add the persisted pump-to-port relationship without changing readings."""

        payload = SensorHistoryRead.model_validate(item).model_dump()
        payload["communication_port_id"] = communication_port_id
        return payload

    @staticmethod
    def filters(from_time: datetime | None, to_time: datetime | None, limit: int) -> dict[str, object]:
        now = utc_now()
        start, end = from_time or now - timedelta(minutes=10), to_time or now
        if start > end:
            raise BusinessRuleError("from must not be later than to.")
        return {"from_time": start, "to_time": end, "limit": limit}

    def _station(self, station_id: int) -> None:
        if StationRepository(self.db).get(station_id) is None:
            raise NotFoundError("Station not found.")
