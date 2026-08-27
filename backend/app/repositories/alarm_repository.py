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

    def list(self, *, include_false_positives: bool = False) -> list[Alarm]:
        statement = select(Alarm)
        # False positives are audit records, not active operational work.  Keep
        # them durable while making the default queue safe to act on.
        if not include_false_positives:
            statement = statement.where(Alarm.status != AlarmStatus.FALSE_POSITIVE)
        return list(self.db.scalars(statement.order_by(Alarm.detected_at.desc())))

    def active_for_key(
        self, station_id: int, target_type: str, target_id: int, alarm_type: str
    ) -> Alarm | None:
        target_filter = (
            Alarm.tank_id == target_id
            if target_type == "TANK"
            else Alarm.pump_id == target_id
            if target_type == "PUMP"
            else (Alarm.target_type == target_type) & (Alarm.target_id == target_id)
        )
        return self.db.scalar(
            select(Alarm).where(
                Alarm.station_id == station_id,
                target_filter,
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
