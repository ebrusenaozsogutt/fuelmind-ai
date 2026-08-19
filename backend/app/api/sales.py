"""Sale API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.sale import CommercialSaleRequest, CommercialSaleResponse, SaleCreate, SaleRead
from app.services.commercial_sale_service import CommercialSaleService
from app.services.sale_service import SaleService

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("", response_model=list[SaleRead])
def list_sales(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    customer_id: int | None = Query(default=None, gt=0),
    vehicle_id: int | None = Query(default=None, gt=0),
    fuel_card_id: int | None = Query(default=None, gt=0),
) -> list[object]:
    return SaleService(db).list(
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        fuel_card_id=fuel_card_id,
    )[skip : skip + limit]


@router.post("", response_model=SaleRead, status_code=status.HTTP_201_CREATED)
def create_sale(
    payload: SaleCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return SaleService(db).create(payload)


@router.post("/commercial", response_model=CommercialSaleResponse)
def create_commercial_sale(
    payload: CommercialSaleRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> CommercialSaleResponse:
    """Authorize and immediately complete one card-backed commercial sale."""

    return CommercialSaleService(db).complete(payload)


@router.get("/{sale_id}", response_model=SaleRead)
def get_sale(
    sale_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return SaleService(db).get(sale_id)
