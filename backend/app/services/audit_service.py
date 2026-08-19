"""Central, transaction-bound immutable audit recording."""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.utils.enums import AuditAction


_SENSITIVE = {"password", "password_hash", "secret", "token", "jwt"}


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(self, *, action: AuditAction, entity_type: str, entity_id: int, user_id: int | None = None, username: str | None = None, station_id: int | None = None, old_values: dict[str, object] | None = None, new_values: dict[str, object] | None = None, description: str | None = None) -> None:
        try:
            # Use the current transaction's connection.  Inspecting the
            # Engine may borrow/return a separate SQLite StaticPool connection
            # and inadvertently roll back the in-flight service transaction.
            audit_table_exists = inspect(self.db.connection()).has_table("audit_logs")
        except (AttributeError, TypeError):
            # Lightweight unit-test sessions without an engine should retain
            # the existing service behavior rather than require audit setup.
            return
        if not audit_table_exists:
            return
        self.db.add(AuditLog(user_id=user_id, username_snapshot=username, action=action, entity_type=entity_type, entity_id=entity_id, station_id=station_id, old_values_json=self._safe(old_values), new_values_json=self._safe(new_values), description=description))

    @classmethod
    def _safe(cls, values: dict[str, object] | None) -> dict[str, object] | None:
        if values is None:
            return None
        return {key: cls._json(value) for key, value in values.items() if key.lower() not in _SENSITIVE}

    @classmethod
    def _json(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, dict):
            return cls._safe(value) or {}
        if isinstance(value, (list, tuple)):
            return [cls._json(item) for item in value]
        return value
