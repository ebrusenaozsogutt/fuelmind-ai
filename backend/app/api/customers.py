"""Customer management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerDetailRead, CustomerRead, CustomerUpdate
from app.schemas.customer_authorized_person import CustomerAuthorizedPersonRead
from app.schemas.fleet import FleetRead
from app.services.customer_authorized_person_service import CustomerAuthorizedPersonService
from app.services.customer_service import CustomerService
from app.services.fleet_service import FleetService
from app.utils.enums import CustomerRequestStatus, CustomerType

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=list[CustomerRead])
def list_customers(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    customer_type: CustomerType | None = None,
    is_active: bool | None = None,
    request_status: CustomerRequestStatus | None = None,
    sector: str | None = None,
    search: str | None = None,
) -> list[object]:
    items = CustomerService(db).list(
        customer_type=customer_type,
        is_active=is_active,
        request_status=request_status,
        sector=sector,
        search=search,
    )
    return items[skip : skip + limit]


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return CustomerService(db).create(payload)


@router.get("/{customer_id}/authorized-persons", response_model=list[CustomerAuthorizedPersonRead])
def list_customer_authorized_persons(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[object]:
    return CustomerAuthorizedPersonService(db).list(customer_id=customer_id)


@router.get("/{customer_id}/fleets", response_model=list[FleetRead])
def list_customer_fleets(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[object]:
    return FleetService(db).list(customer_id=customer_id)


@router.get("/{customer_id}/detail", response_model=CustomerDetailRead)
def get_customer_detail(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> dict[str, object]:
    customer = CustomerService(db).get(customer_id)
    return {
        "customer": customer,
        "authorized_persons": CustomerAuthorizedPersonService(db).list(
            customer_id=customer_id
        ),
        "fleets": FleetService(db).list(customer_id=customer_id),
    }


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return CustomerService(db).get(customer_id)


@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return CustomerService(db).update(customer_id, payload)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_customer(
    customer_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    CustomerService(db).deactivate(customer_id)
