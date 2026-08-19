"""Fault lifecycle endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.fault import FaultCreate, FaultRead, FaultResolution
from app.services.fault_service import FaultService
from app.utils.enums import FaultCode, FaultStatus, FaultTargetType, FaultType

router = APIRouter(prefix="/faults", tags=["faults"])


@router.get("", response_model=list[FaultRead])
def list_faults(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    station_id: int | None = Query(default=None, gt=0),
    fault_type: FaultType | None = None,
    fault_code: FaultCode | None = None,
    status_filter: FaultStatus | None = Query(default=None, alias="status"),
    target_type: FaultTargetType | None = None,
    target_id: int | None = Query(default=None, gt=0),
    alarm_id: int | None = Query(default=None, gt=0),
    detected_from: datetime | None = None,
    detected_to: datetime | None = None,
) -> list[object]:
    return FaultService(db).list(station_id=station_id, fault_type=fault_type, fault_code=fault_code, status=status_filter, target_type=target_type, target_id=target_id, alarm_id=alarm_id, detected_from=detected_from, detected_to=detected_to)


@router.post("", response_model=FaultRead, status_code=status.HTTP_201_CREATED)
def create_fault(payload: FaultCreate, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_operator_or_admin)]) -> object:
    return FaultService(db).create(payload, user_id=user.id, username=user.username)


@router.get("/{fault_id}", response_model=FaultRead)
def get_fault(fault_id: int, db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)]) -> object:
    return FaultService(db).get(fault_id)


@router.patch("/{fault_id}/investigate", response_model=FaultRead)
def investigate_fault(fault_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_operator_or_admin)]) -> object:
    return FaultService(db).investigate(fault_id, user_id=user.id, username=user.username)


@router.patch("/{fault_id}/resolve", response_model=FaultRead)
def resolve_fault(fault_id: int, payload: FaultResolution, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_operator_or_admin)]) -> object:
    return FaultService(db).resolve(fault_id, user_id=user.id, username=user.username, resolution_note=payload.resolution_note)
