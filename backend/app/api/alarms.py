"""Operational alarm query and lifecycle endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.dependencies import require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.alarm import AlarmRead, AlarmResolution
from app.services.alarm_service import AlarmService
from app.utils.enums import AlarmStatus

router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("", response_model=list[AlarmRead])
def list_alarms(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
):
    return AlarmService(db).list()


@router.get("/{alarm_id}", response_model=AlarmRead)
def get_alarm(
    alarm_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
):
    return AlarmService(db).get(alarm_id)


def _transition(
    alarm_id: int,
    target: AlarmStatus,
    payload: AlarmResolution,
    db: Session,
    user: User,
):
    return AlarmService(db).transition(
        alarm_id, target, user.id, payload.resolution_note
    )


@router.patch("/{alarm_id}/acknowledge", response_model=AlarmRead)
def acknowledge(
    alarm_id: int,
    payload: AlarmResolution,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_operator_or_admin)],
):
    return _transition(alarm_id, AlarmStatus.ACKNOWLEDGED, payload, db, user)


@router.patch("/{alarm_id}/investigate", response_model=AlarmRead)
def investigate(
    alarm_id: int,
    payload: AlarmResolution,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_operator_or_admin)],
):
    return _transition(alarm_id, AlarmStatus.INVESTIGATING, payload, db, user)


@router.patch("/{alarm_id}/resolve", response_model=AlarmRead)
def resolve(
    alarm_id: int,
    payload: AlarmResolution,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_operator_or_admin)],
):
    return _transition(alarm_id, AlarmStatus.RESOLVED, payload, db, user)


@router.patch("/{alarm_id}/false-positive", response_model=AlarmRead)
def false_positive(
    alarm_id: int,
    payload: AlarmResolution,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_operator_or_admin)],
):
    return _transition(alarm_id, AlarmStatus.FALSE_POSITIVE, payload, db, user)
