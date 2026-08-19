"""Driver management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.driver import DriverCreate, DriverRead, DriverUpdate
from app.schemas.driver_vehicle_assignment import DriverVehicleAssignmentRead
from app.services.driver_service import DriverService
from app.services.driver_vehicle_assignment_service import DriverVehicleAssignmentService

router = APIRouter(prefix="/drivers", tags=["Drivers"])


@router.get("", response_model=list[DriverRead])
def list_drivers(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[object]:
    items = DriverService(db).list(is_active=is_active, search=search)
    return items[skip : skip + limit]


@router.post("", response_model=DriverRead, status_code=status.HTTP_201_CREATED)
def create_driver(
    payload: DriverCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return DriverService(db).create(payload)


@router.get("/{driver_id}/vehicle-assignments", response_model=list[DriverVehicleAssignmentRead])
def list_driver_assignments(
    driver_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[object]:
    return DriverVehicleAssignmentService(db).list(driver_id=driver_id)


@router.get("/{driver_id}", response_model=DriverRead)
def get_driver(
    driver_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return DriverService(db).get(driver_id)


@router.put("/{driver_id}", response_model=DriverRead)
def update_driver(
    driver_id: int,
    payload: DriverUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return DriverService(db).update(driver_id, payload)


@router.delete("/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_driver(
    driver_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    DriverService(db).deactivate(driver_id)
