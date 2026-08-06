"""Fuel type API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.fuel_type import FuelTypeCreate, FuelTypeRead, FuelTypeUpdate
from app.services.fuel_type_service import FuelTypeService

router = APIRouter(prefix="/fuel-types", tags=["fuel types"])


def _page(
    items: list[object], skip: int, limit: int, is_active: bool | None
) -> list[object]:
    if is_active is not None:
        items = [item for item in items if item.is_active == is_active]
    return items[skip : skip + limit]


@router.get("", response_model=list[FuelTypeRead])
def list_fuel_types(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    return _page(FuelTypeService(db).list(), skip, limit, is_active)


@router.post("", response_model=FuelTypeRead, status_code=status.HTTP_201_CREATED)
def create_fuel_type(
    payload: FuelTypeCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return FuelTypeService(db).create(payload)


@router.get("/{fuel_type_id}", response_model=FuelTypeRead)
def get_fuel_type(
    fuel_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return FuelTypeService(db).get(fuel_type_id)


@router.put("/{fuel_type_id}", response_model=FuelTypeRead)
def update_fuel_type(
    fuel_type_id: int,
    payload: FuelTypeUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return FuelTypeService(db).update(fuel_type_id, payload)


@router.delete("/{fuel_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_fuel_type(
    fuel_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    FuelTypeService(db).deactivate(fuel_type_id)
