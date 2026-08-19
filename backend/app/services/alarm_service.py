"""Transactional alarm state transitions."""

from sqlalchemy.orm import Session
from app.exceptions import BusinessRuleError, NotFoundError
from app.repositories.alarm_repository import AlarmRepository
from app.utils.datetime_utils import utc_now
from app.utils.enums import AlarmStatus


class AlarmService:
    def __init__(self, db: Session) -> None:
        self.db, self.repository = db, AlarmRepository(db)

    def get(self, alarm_id: int):
        alarm = self.repository.get(alarm_id)
        if alarm is None:
            raise NotFoundError("Alarm not found.")
        return alarm

    def list(self, *, include_false_positives: bool = False):
        return self.repository.list(include_false_positives=include_false_positives)

    def transition(
        self, alarm_id: int, target: AlarmStatus, user_id: int, note: str | None = None
    ):
        alarm = self.get(alarm_id)
        allowed = {
            AlarmStatus.NEW: {
                AlarmStatus.ACKNOWLEDGED,
                AlarmStatus.INVESTIGATING,
                AlarmStatus.RESOLVED,
                AlarmStatus.FALSE_POSITIVE,
            },
            AlarmStatus.ACKNOWLEDGED: {
                AlarmStatus.INVESTIGATING,
                AlarmStatus.RESOLVED,
                AlarmStatus.FALSE_POSITIVE,
            },
            AlarmStatus.INVESTIGATING: {
                AlarmStatus.RESOLVED,
                AlarmStatus.FALSE_POSITIVE,
            },
        }
        if target not in allowed.get(alarm.status, set()):
            raise BusinessRuleError("Invalid alarm status transition.")
        alarm.status = target
        if target == AlarmStatus.ACKNOWLEDGED:
            alarm.acknowledged_at = utc_now()
        if target in {AlarmStatus.RESOLVED, AlarmStatus.FALSE_POSITIVE}:
            alarm.resolved_at, alarm.resolved_by, alarm.resolution_note = (
                utc_now(),
                user_id,
                note,
            )
        self.db.commit()
        self.db.refresh(alarm)
        return alarm
