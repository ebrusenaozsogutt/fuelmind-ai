"""Fleet-group management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.fleet_group import FleetGroupCreate, FleetGroupRead, FleetGroupUpdate
from app.schemas.vehicle import VehicleRead
from app.services.fleet_group_service import FleetGroupService
from app.services.vehicle_service import VehicleService

router = APIRouter(prefix="/fleet-groups", tags=["Fleet Groups"])


@router.get("", response_model=list[FleetGroupRead])
def list_fleet_groups(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    fleet_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
) -> list[object]:
    items = FleetGroupService(db).list(fleet_id=fleet_id, is_active=is_active)
    return items[skip : skip + limit]


@router.post("", response_model=FleetGroupRead, status_code=status.HTTP_201_CREATED)
def create_fleet_group(
    payload: FleetGroupCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return FleetGroupService(db).create(payload)


@router.get("/{fleet_group_id}/vehicles", response_model=list[VehicleRead])
def list_fleet_group_vehicles(
    fleet_group_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[object]:
    return VehicleService(db).list(fleet_group_id=fleet_group_id)


@router.get("/{group_id}", response_model=FleetGroupRead)
def get_fleet_group(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return FleetGroupService(db).get(group_id)


@router.put("/{group_id}", response_model=FleetGroupRead)
def update_fleet_group(
    group_id: int,
    payload: FleetGroupUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return FleetGroupService(db).update(group_id, payload)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_fleet_group(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    FleetGroupService(db).deactivate(group_id)
