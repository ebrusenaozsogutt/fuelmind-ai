"""Customer authorized-person management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.customer_authorized_person import (
    CustomerAuthorizedPersonCreate,
    CustomerAuthorizedPersonRead,
    CustomerAuthorizedPersonUpdate,
)
from app.services.customer_authorized_person_service import CustomerAuthorizedPersonService

router = APIRouter(
    prefix="/customer-authorized-persons", tags=["Customer Authorized Persons"]
)


@router.get("", response_model=list[CustomerAuthorizedPersonRead])
def list_authorized_persons(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    customer_id: int | None = Query(default=None, gt=0),
) -> list[object]:
    items = CustomerAuthorizedPersonService(db).list(customer_id=customer_id)
    return items[skip : skip + limit]


@router.post("", response_model=CustomerAuthorizedPersonRead, status_code=status.HTTP_201_CREATED)
def create_authorized_person(
    payload: CustomerAuthorizedPersonCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return CustomerAuthorizedPersonService(db).create(payload)


@router.get("/{person_id}", response_model=CustomerAuthorizedPersonRead)
def get_authorized_person(
    person_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return CustomerAuthorizedPersonService(db).get(person_id)


@router.put("/{person_id}", response_model=CustomerAuthorizedPersonRead)
def update_authorized_person(
    person_id: int,
    payload: CustomerAuthorizedPersonUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return CustomerAuthorizedPersonService(db).update(person_id, payload)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_authorized_person(
    person_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    CustomerAuthorizedPersonService(db).deactivate(person_id)
