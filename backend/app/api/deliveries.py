"""Delivery API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.delivery import DeliveryCreate, DeliveryRead
from app.services.delivery_service import DeliveryService

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get("", response_model=list[DeliveryRead])
def list_deliveries(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[object]:
    return DeliveryService(db).list()[skip : skip + limit]


@router.post("", response_model=DeliveryRead, status_code=status.HTTP_201_CREATED)
def create_delivery(
    payload: DeliveryCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return DeliveryService(db).create(payload)


@router.get("/{delivery_id}", response_model=DeliveryRead)
def get_delivery(
    delivery_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return DeliveryService(db).get(delivery_id)
