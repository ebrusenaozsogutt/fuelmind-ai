"""Audited mutations for attendant and shift operational records."""

from typing import Any

from sqlalchemy.orm import Session

from app.exceptions import BusinessRuleError, NotFoundError
from app.models.operations import Attendant, Shift
from app.services.audit_service import AuditService
from app.utils.enums import AuditAction


class OperationsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def update_attendant(
        self,
        attendant_id: int,
        values: dict[str, Any],
        *,
        user_id: int | None,
        username: str | None,
    ) -> Attendant:
        attendant = self._get(Attendant, attendant_id)
        old_values = {key: getattr(attendant, key) for key in values}
        for key, value in values.items():
            setattr(attendant, key, value)
        action = AuditAction.STATUS_CHANGE if "is_active" in values else AuditAction.UPDATE
        AuditService(self.db).record(
            action=action,
            entity_type="ATTENDANT",
            entity_id=attendant.id,
            user_id=user_id,
            username=username,
            station_id=attendant.station_id,
            old_values=old_values,
            new_values={key: getattr(attendant, key) for key in values},
            description="Attendant active status changed" if "is_active" in values else "Attendant changed",
        )
        return self._commit(attendant)

    def deactivate_attendant(
        self, attendant_id: int, *, user_id: int | None, username: str | None
    ) -> Attendant:
        return self.update_attendant(
            attendant_id,
            {"is_active": False},
            user_id=user_id,
            username=username,
        )

    def update_shift(
        self,
        shift_id: int,
        values: dict[str, Any],
        *,
        user_id: int | None,
        username: str | None,
    ) -> Shift:
        shift = self._get(Shift, shift_id)
        start_time = values.get("start_time", shift.start_time)
        end_time = values.get("end_time", shift.end_time)
        if start_time == end_time:
            raise BusinessRuleError("Shift start and end times cannot be equal.")
        old_values = {key: getattr(shift, key) for key in values}
        for key, value in values.items():
            setattr(shift, key, value)
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="SHIFT",
            entity_id=shift.id,
            user_id=user_id,
            username=username,
            station_id=shift.station_id,
            old_values=old_values,
            new_values={key: getattr(shift, key) for key in values},
            description="Shift changed",
        )
        return self._commit(shift)

    def deactivate_shift(
        self, shift_id: int, *, user_id: int | None, username: str | None
    ) -> Shift:
        return self.update_shift(
            shift_id,
            {"is_active": False},
            user_id=user_id,
            username=username,
        )

    def _get(self, model: type[Attendant] | type[Shift], entity_id: int) -> Attendant | Shift:
        entity = self.db.get(model, entity_id)
        if entity is None:
            raise NotFoundError(f"{model.__name__} not found.")
        return entity

    def _commit(self, entity: Attendant | Shift) -> Attendant | Shift:
        try:
            self.db.commit()
            self.db.refresh(entity)
            return entity
        except Exception:
            self.db.rollback()
            raise
