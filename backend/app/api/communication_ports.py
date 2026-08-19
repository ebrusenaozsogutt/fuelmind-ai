"""Management API endpoints for controller communication ports."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.communication_port import (
    CommunicationPortCreate,
    CommunicationPortRead,
    CommunicationPortUpdate,
)
from app.services.communication_port_service import CommunicationPortService

router = APIRouter(tags=["Communication Ports"])


def _page(
    items: list[object], skip: int, limit: int, is_active: bool | None
) -> list[object]:
    if is_active is not None:
        items = [item for item in items if item.is_active == is_active]
    return items[skip : skip + limit]


@router.get("/communication-ports", response_model=list[CommunicationPortRead])
def list_communication_ports(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    return _page(CommunicationPortService(db).list(), skip, limit, is_active)


@router.post(
    "/communication-ports",
    response_model=CommunicationPortRead,
    status_code=status.HTTP_201_CREATED,
)
def create_communication_port(
    payload: CommunicationPortCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return CommunicationPortService(db).create(payload)


@router.get(
    "/device-controllers/{controller_id}/ports",
    response_model=list[CommunicationPortRead],
)
def list_controller_ports(
    controller_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    return _page(
        CommunicationPortService(db).list_by_controller(controller_id),
        skip,
        limit,
        is_active,
    )


@router.get("/communication-ports/{port_id}", response_model=CommunicationPortRead)
def get_communication_port(
    port_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return CommunicationPortService(db).get(port_id)


@router.put("/communication-ports/{port_id}", response_model=CommunicationPortRead)
def update_communication_port(
    port_id: int,
    payload: CommunicationPortUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return CommunicationPortService(db).update(port_id, payload)


@router.delete("/communication-ports/{port_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_communication_port(
    port_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    CommunicationPortService(db).deactivate(port_id)
