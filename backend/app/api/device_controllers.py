"""Management API endpoints for station device controllers."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.device_controller import (
    DeviceControllerCreate,
    DeviceControllerRead,
    DeviceControllerUpdate,
)
from app.services.device_controller_service import DeviceControllerService

router = APIRouter(tags=["Device Controllers"])


def _page(
    items: list[object], skip: int, limit: int, is_active: bool | None
) -> list[object]:
    if is_active is not None:
        items = [item for item in items if item.is_active == is_active]
    return items[skip : skip + limit]


@router.get("/device-controllers", response_model=list[DeviceControllerRead])
def list_device_controllers(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    return _page(DeviceControllerService(db).list(), skip, limit, is_active)


@router.post(
    "/device-controllers",
    response_model=DeviceControllerRead,
    status_code=status.HTTP_201_CREATED,
)
def create_device_controller(
    payload: DeviceControllerCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return DeviceControllerService(db).create(payload)


@router.get(
    "/stations/{station_id}/device-controllers",
    response_model=list[DeviceControllerRead],
)
def list_station_device_controllers(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    return _page(
        DeviceControllerService(db).list_by_station(station_id), skip, limit, is_active
    )


@router.get("/device-controllers/{controller_id}", response_model=DeviceControllerRead)
def get_device_controller(
    controller_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return DeviceControllerService(db).get(controller_id)


@router.put("/device-controllers/{controller_id}", response_model=DeviceControllerRead)
def update_device_controller(
    controller_id: int,
    payload: DeviceControllerUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return DeviceControllerService(db).update(controller_id, payload)


@router.delete("/device-controllers/{controller_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_device_controller(
    controller_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    DeviceControllerService(db).deactivate(controller_id)
