"""Station API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.station import StationCreate, StationRead, StationUpdate
from app.services.station_service import StationService

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("", response_model=list[StationRead])
def list_stations(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    items = StationService(db).list()
    if is_active is not None:
        items = [item for item in items if item.is_active == is_active]
    return items[skip : skip + limit]


@router.post("", response_model=StationRead, status_code=status.HTTP_201_CREATED)
def create_station(
    payload: StationCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return StationService(db).create(payload)


@router.get("/{station_id}", response_model=StationRead)
def get_station(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return StationService(db).get(station_id)


@router.put("/{station_id}", response_model=StationRead)
def update_station(
    station_id: int,
    payload: StationUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return StationService(db).update(station_id, payload)


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_station(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    StationService(db).deactivate(station_id)
