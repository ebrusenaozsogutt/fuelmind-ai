"""Vehicle management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.driver_vehicle_assignment import DriverVehicleAssignmentRead
from app.schemas.driver import DriverRead
from app.schemas.vehicle import VehicleCreate, VehicleRead, VehicleUpdate
from app.services.driver_vehicle_assignment_service import DriverVehicleAssignmentService
from app.services.vehicle_service import VehicleService

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("", response_model=list[VehicleRead])
def list_vehicles(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    fleet_group_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
    search: str | None = None,
) -> list[object]:
    items = VehicleService(db).list(
        fleet_group_id=fleet_group_id, is_active=is_active, search=search
    )
    return items[skip : skip + limit]


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    payload: VehicleCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return VehicleService(db).create(payload)


@router.get("/{vehicle_id}/driver-assignments", response_model=list[DriverVehicleAssignmentRead])
def list_vehicle_assignments(
    vehicle_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[object]:
    return DriverVehicleAssignmentService(db).list(vehicle_id=vehicle_id)


@router.get("/{vehicle_id}/current-driver", response_model=DriverRead | None)
def get_current_driver(
    vehicle_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object | None:
    assignment = DriverVehicleAssignmentService(db).current_for_vehicle(vehicle_id)
    return assignment.driver if assignment is not None else None


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(
    vehicle_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return VehicleService(db).get(vehicle_id)


@router.put("/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return VehicleService(db).update(vehicle_id, payload)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_vehicle(
    vehicle_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    VehicleService(db).deactivate(vehicle_id)
