"""Tank API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.exceptions import BusinessRuleError
from app.models.user import User
from app.schemas.tank import TankCreate, TankRead, TankUpdate
from app.services.station_service import StationService
from app.services.tank_service import TankService

router = APIRouter(tags=["tanks"])


@router.get("/stations/{station_id}/tanks", response_model=list[TankRead])
def list_station_tanks(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    StationService(db).get(station_id)
    items = [tank for tank in TankService(db).list() if tank.station_id == station_id]
    if is_active is not None:
        items = [tank for tank in items if tank.is_active == is_active]
    return items[skip : skip + limit]


@router.post(
    "/stations/{station_id}/tanks",
    response_model=TankRead,
    status_code=status.HTTP_201_CREATED,
)
def create_station_tank(
    station_id: int,
    payload: TankCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    if payload.station_id != station_id:
        raise BusinessRuleError("Payload station_id must match the URL station_id.")
    return TankService(db).create(payload)


@router.get("/tanks/{tank_id}", response_model=TankRead)
def get_tank(
    tank_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return TankService(db).get(tank_id)


@router.put("/tanks/{tank_id}", response_model=TankRead)
def update_tank(
    tank_id: int,
    payload: TankUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return TankService(db).update(tank_id, payload)


@router.delete("/tanks/{tank_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_tank(
    tank_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    TankService(db).deactivate(tank_id)
