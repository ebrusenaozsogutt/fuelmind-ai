"""Driver vehicle assignment API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.driver_vehicle_assignment import (
    DriverVehicleAssignmentCreate,
    DriverVehicleAssignmentRead,
    DriverVehicleAssignmentUpdate,
)
from app.services.driver_vehicle_assignment_service import DriverVehicleAssignmentService

router = APIRouter(
    prefix="/driver-vehicle-assignments", tags=["Driver Vehicle Assignments"]
)


@router.get("", response_model=list[DriverVehicleAssignmentRead])
def list_assignments(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    driver_id: int | None = Query(default=None, gt=0),
    vehicle_id: int | None = Query(default=None, gt=0),
) -> list[object]:
    items = DriverVehicleAssignmentService(db).list(
        driver_id=driver_id, vehicle_id=vehicle_id
    )
    return items[skip : skip + limit]


@router.post(
    "", response_model=DriverVehicleAssignmentRead, status_code=status.HTTP_201_CREATED
)
def create_assignment(
    payload: DriverVehicleAssignmentCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return DriverVehicleAssignmentService(db).create(payload)


@router.get("/{assignment_id}", response_model=DriverVehicleAssignmentRead)
def get_assignment(
    assignment_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return DriverVehicleAssignmentService(db).get(assignment_id)


@router.put("/{assignment_id}", response_model=DriverVehicleAssignmentRead)
def update_assignment(
    assignment_id: int,
    payload: DriverVehicleAssignmentUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return DriverVehicleAssignmentService(db).update(assignment_id, payload)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_assignment(
    assignment_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    DriverVehicleAssignmentService(db).cancel(assignment_id)
