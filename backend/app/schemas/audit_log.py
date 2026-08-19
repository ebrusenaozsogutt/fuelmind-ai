"""Read-only audit-log API contract."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.utils.enums import AuditAction


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None
    username_snapshot: str | None
    action: AuditAction
    entity_type: str
    entity_id: int
    station_id: int | None
    old_values_json: dict[str, Any] | None
    new_values_json: dict[str, Any] | None
    description: str | None
    created_at: datetime
