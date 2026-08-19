"""Fuel price history management and read-only pricing preview endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.fuel_price import (
    FuelPriceCreate,
    FuelPriceRead,
    FuelPriceUpdate,
    SalePriceCalculationRequest,
    SalePriceCalculationResult,
)
from app.services.fuel_price_service import FuelPriceService, FuelPricingService
from app.utils.datetime_utils import utc_now


router = APIRouter(tags=["Fuel Prices"])


@router.post(
    "/fuel-prices/calculate-sale-price", response_model=SalePriceCalculationResult
)
def calculate_sale_price(
    payload: SalePriceCalculationRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> SalePriceCalculationResult:
    """Preview the snapshot values for a sale without changing any records."""

    return FuelPricingService(db).calculate_sale_price(**payload.model_dump())


@router.get("/fuel-prices", response_model=list[FuelPriceRead])
def list_fuel_prices(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    station_id: int | None = Query(default=None, gt=0),
    fuel_type_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[object]:
    items = FuelPriceService(db).list(
        station_id=station_id,
        fuel_type_id=fuel_type_id,
        is_active=is_active,
    )
    return items[skip : skip + limit]


@router.post("/fuel-prices", response_model=FuelPriceRead, status_code=status.HTTP_201_CREATED)
def create_fuel_price(
    payload: FuelPriceCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> object:
    return FuelPriceService(db).set_price(
        payload, created_by=user.id, username=user.username
    )


@router.get(
    "/stations/{station_id}/fuel-prices", response_model=list[FuelPriceRead]
)
def list_station_fuel_prices(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    fuel_type_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
) -> list[object]:
    return FuelPriceService(db).list(
        station_id=station_id,
        fuel_type_id=fuel_type_id,
        is_active=is_active,
    )


@router.get(
    "/stations/{station_id}/fuel-prices/{fuel_type_id}/current",
    response_model=FuelPriceRead,
)
def current_fuel_price(
    station_id: int,
    fuel_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    at: datetime | None = None,
) -> object:
    return FuelPriceService(db).current(
        station_id,
        fuel_type_id,
        at if at is not None else utc_now(),
    )


@router.get(
    "/stations/{station_id}/fuel-prices/{fuel_type_id}/history",
    response_model=list[FuelPriceRead],
)
def fuel_price_history(
    station_id: int,
    fuel_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> list[object]:
    return FuelPriceService(db).history(station_id, fuel_type_id)


@router.get("/fuel-prices/{fuel_price_id}", response_model=FuelPriceRead)
def get_fuel_price(
    fuel_price_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return FuelPriceService(db).get(fuel_price_id)


@router.put("/fuel-prices/{fuel_price_id}", response_model=FuelPriceRead)
def update_fuel_price(
    fuel_price_id: int,
    payload: FuelPriceUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> object:
    return FuelPriceService(db).update(fuel_price_id, payload, user_id=user.id, username=user.username)


@router.delete("/fuel-prices/{fuel_price_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_fuel_price(
    fuel_price_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    FuelPriceService(db).deactivate(fuel_price_id)
