"""Fleet management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.fleet import FleetCreate, FleetRead, FleetUpdate
from app.services.fleet_group_service import FleetGroupService
from app.services.fleet_service import FleetService
from app.schemas.fleet_group import FleetGroupRead
from app.utils.enums import CustomerRequestStatus

router = APIRouter(prefix="/fleets", tags=["Fleets"])


@router.get("", response_model=list[FleetRead])
def list_fleets(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    customer_id: int | None = Query(default=None, gt=0),
    request_status: CustomerRequestStatus | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[object]:
    items = FleetService(db).list(
        customer_id=customer_id,
        request_status=request_status,
        is_active=is_active,
        search=search,
    )
    return items[skip : skip + limit]


@router.post("", response_model=FleetRead, status_code=status.HTTP_201_CREATED)
def create_fleet(
    payload: FleetCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return FleetService(db).create(payload)


@router.get("/{fleet_id}/groups", response_model=list[FleetGroupRead])
def list_fleet_groups(
    fleet_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[object]:
    return FleetGroupService(db).list(fleet_id=fleet_id)


@router.get("/{fleet_id}", response_model=FleetRead)
def get_fleet(
    fleet_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return FleetService(db).get(fleet_id)


@router.put("/{fleet_id}", response_model=FleetRead)
def update_fleet(
    fleet_id: int,
    payload: FleetUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return FleetService(db).update(fleet_id, payload)


@router.delete("/{fleet_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_fleet(
    fleet_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    FleetService(db).deactivate(fleet_id)
