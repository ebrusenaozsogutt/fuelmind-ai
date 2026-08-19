"""Admin-only, immutable audit-log read API."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogRead
from app.utils.enums import AuditAction

router = APIRouter(prefix="/audit-logs", tags=["audit logs"])


@router.get("", response_model=list[AuditLogRead])
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    user_id: int | None = Query(default=None, gt=0),
    entity_type: str | None = None,
    entity_id: int | None = Query(default=None, gt=0),
    station_id: int | None = Query(default=None, gt=0),
    action: AuditAction | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[object]:
    query = select(AuditLog)
    filters = (
        (AuditLog.user_id, user_id),
        (AuditLog.entity_type, entity_type),
        (AuditLog.entity_id, entity_id),
        (AuditLog.station_id, station_id),
        (AuditLog.action, action),
    )
    for column, value in filters:
        if value is not None:
            query = query.where(column == value)
    if created_from is not None:
        query = query.where(AuditLog.created_at >= created_from)
    if created_to is not None:
        query = query.where(AuditLog.created_at <= created_to)
    return list(db.scalars(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())))
