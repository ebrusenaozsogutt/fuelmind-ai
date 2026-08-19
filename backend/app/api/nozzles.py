"""Management API endpoints for pump nozzles."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.nozzle import NozzleCreate, NozzleRead, NozzleUpdate
from app.services.nozzle_service import NozzleService

router = APIRouter(tags=["Nozzles"])


def _page(
    items: list[object], skip: int, limit: int, is_active: bool | None
) -> list[object]:
    if is_active is not None:
        items = [item for item in items if item.is_active == is_active]
    return items[skip : skip + limit]


@router.get("/nozzles", response_model=list[NozzleRead])
def list_nozzles(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    return _page(NozzleService(db).list(), skip, limit, is_active)


@router.post("/nozzles", response_model=NozzleRead, status_code=status.HTTP_201_CREATED)
def create_nozzle(
    payload: NozzleCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return NozzleService(db).create(payload)


@router.get("/pumps/{pump_id}/nozzles", response_model=list[NozzleRead])
def list_pump_nozzles(
    pump_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    return _page(NozzleService(db).list_by_pump(pump_id), skip, limit, is_active)


@router.get("/nozzles/{nozzle_id}", response_model=NozzleRead)
def get_nozzle(
    nozzle_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return NozzleService(db).get(nozzle_id)


@router.put("/nozzles/{nozzle_id}", response_model=NozzleRead)
def update_nozzle(
    nozzle_id: int,
    payload: NozzleUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return NozzleService(db).update(nozzle_id, payload)


@router.delete("/nozzles/{nozzle_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_nozzle(
    nozzle_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    NozzleService(db).deactivate(nozzle_id)
