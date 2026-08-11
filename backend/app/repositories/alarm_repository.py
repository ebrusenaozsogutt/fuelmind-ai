"""Alarm queries including active-key deduplication."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.alarm import Alarm
from app.utils.enums import AlarmStatus


class AlarmRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, alarm_id: int) -> Alarm | None:
        return self.db.get(Alarm, alarm_id)

    def list(self) -> list[Alarm]:
        return list(self.db.scalars(select(Alarm).order_by(Alarm.detected_at.desc())))

    def active_for_key(
        self, station_id: int, target_type: str, target_id: int, alarm_type: str
    ) -> Alarm | None:
        field = Alarm.tank_id if target_type == "TANK" else Alarm.pump_id
        return self.db.scalar(
            select(Alarm).where(
                Alarm.station_id == station_id,
                field == target_id,
                Alarm.alarm_type == alarm_type,
                Alarm.status.in_(
                    (
                        AlarmStatus.NEW,
                        AlarmStatus.ACKNOWLEDGED,
                        AlarmStatus.INVESTIGATING,
                    )
                ),
            )
        )

    def create(self, values: dict[str, object]) -> Alarm:
        entity = Alarm(**values)
        self.db.add(entity)
        self.db.flush()
        return entity
