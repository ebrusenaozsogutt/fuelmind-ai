"""Pump API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.exceptions import BusinessRuleError
from app.models.user import User
from app.schemas.pump import PumpCreate, PumpRead, PumpUpdate
from app.services.pump_service import PumpService
from app.services.station_service import StationService

router = APIRouter(tags=["pumps"])


@router.get("/stations/{station_id}/pumps", response_model=list[PumpRead])
def list_station_pumps(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    StationService(db).get(station_id)
    items = [pump for pump in PumpService(db).list() if pump.station_id == station_id]
    if is_active is not None:
        items = [pump for pump in items if pump.is_active == is_active]
    return items[skip : skip + limit]


@router.post(
    "/stations/{station_id}/pumps",
    response_model=PumpRead,
    status_code=status.HTTP_201_CREATED,
)
def create_station_pump(
    station_id: int,
    payload: PumpCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    if payload.station_id != station_id:
        raise BusinessRuleError("Payload station_id must match the URL station_id.")
    return PumpService(db).create(payload)


@router.get("/pumps/{pump_id}", response_model=PumpRead)
def get_pump(
    pump_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return PumpService(db).get(pump_id)


@router.put("/pumps/{pump_id}", response_model=PumpRead)
def update_pump(
    pump_id: int,
    payload: PumpUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return PumpService(db).update(pump_id, payload)


@router.delete("/pumps/{pump_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_pump(
    pump_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    PumpService(db).deactivate(pump_id)
