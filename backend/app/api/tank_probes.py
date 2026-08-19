"""Management and read-only history API endpoints for tank probes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.probe_reading import ProbeReadingRead
from app.schemas.tank_probe import TankProbeCreate, TankProbeRead, TankProbeUpdate
from app.services.probe_reading_service import ProbeReadingService
from app.services.tank_probe_service import TankProbeService

router = APIRouter(tags=["Tank Probes"])


def _page(
    items: list[object], skip: int, limit: int, is_active: bool | None
) -> list[object]:
    if is_active is not None:
        items = [item for item in items if item.is_active == is_active]
    return items[skip : skip + limit]


@router.get("/tank-probes", response_model=list[TankProbeRead])
def list_tank_probes(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    return _page(TankProbeService(db).list(), skip, limit, is_active)


@router.post(
    "/tank-probes", response_model=TankProbeRead, status_code=status.HTTP_201_CREATED
)
def create_tank_probe(
    payload: TankProbeCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return TankProbeService(db).create(payload)


@router.get("/tanks/{tank_id}/probe", response_model=TankProbeRead)
def get_active_tank_probe(
    tank_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return TankProbeService(db).get_active_by_tank(tank_id)


@router.get("/tank-probes/{probe_id}", response_model=TankProbeRead)
def get_tank_probe(
    probe_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return TankProbeService(db).get(probe_id)


@router.put("/tank-probes/{probe_id}", response_model=TankProbeRead)
def update_tank_probe(
    probe_id: int,
    payload: TankProbeUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return TankProbeService(db).update(probe_id, payload)


@router.delete("/tank-probes/{probe_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_tank_probe(
    probe_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    TankProbeService(db).deactivate(probe_id)


@router.get("/tank-probes/{probe_id}/readings", response_model=list[ProbeReadingRead])
def list_probe_readings(
    probe_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 600,
) -> list[object]:
    return ProbeReadingService(db).list_by_probe(probe_id, start, end, limit)


@router.get("/tanks/{tank_id}/probe-readings", response_model=list[ProbeReadingRead])
def list_tank_probe_readings(
    tank_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 600,
) -> list[object]:
    return ProbeReadingService(db).list_by_tank(tank_id, start, end, limit)
