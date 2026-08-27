"""Tank API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.exceptions import BusinessRuleError
from app.models.user import User
from app.schemas.tank import OrderRecommendationRead, TankCreate, TankRead, TankUpdate
from app.schemas.reconciliation import TankReconciliationRead, TankReconciliationRequest
from app.services.station_service import StationService
from app.services.tank_service import TankService
from app.services.order_planning_service import OrderPlanningService
from app.services.tank_reconciliation_service import TankReconciliationService

router = APIRouter(tags=["tanks"])


@router.get("/stations/{station_id}/tanks", response_model=list[TankRead])
def list_station_tanks(
    station_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    is_active: bool | None = None,
) -> list[object]:
    StationService(db).get(station_id)
    items = [tank for tank in TankService(db).list() if tank.station_id == station_id]
    if is_active is not None:
        items = [tank for tank in items if tank.is_active == is_active]
    return items[skip : skip + limit]


@router.post(
    "/stations/{station_id}/tanks",
    response_model=TankRead,
    status_code=status.HTTP_201_CREATED,
)
def create_station_tank(
    station_id: int,
    payload: TankCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    if payload.station_id != station_id:
        raise BusinessRuleError("Payload station_id must match the URL station_id.")
    return TankService(db).create(payload)


@router.get("/tanks/{tank_id}", response_model=TankRead)
def get_tank(
    tank_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> object:
    return TankService(db).get(tank_id)


@router.post("/tanks/{tank_id}/reconciliation", response_model=TankReconciliationRead)
def reconcile_tank(
    tank_id: int,
    payload: TankReconciliationRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
) -> TankReconciliationRead:
    """Calculate a measured stock reconciliation and deduplicate any mismatch alarm."""

    try:
        result = TankReconciliationService(db).reconcile(
            tank_id=tank_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            opening_level_liters=payload.opening_level_liters,
            actual_closing_level_liters=payload.actual_closing_level_liters,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise

@router.get("/tanks/{tank_id}/recommendation", response_model=OrderRecommendationRead)
def get_recommendation(tank_id: int, db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)]) -> object:
    return _recommendation_read(db, OrderPlanningService(db).latest(tank_id))

@router.post("/tanks/{tank_id}/recommendation/generate", response_model=OrderRecommendationRead)
def generate_recommendation(tank_id: int, db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_admin)]) -> object:
    return _recommendation_read(db, OrderPlanningService(db).generate(tank_id))


def _recommendation_read(db: Session, recommendation: object) -> dict[str, object]:
    """Return recommendation and its tank stock from the same authoritative record."""
    tank = TankService(db).get(recommendation.tank_id)
    return {
        "tank_id": recommendation.tank_id,
        "station_id": recommendation.station_id,
        "current_stock_liters": tank.current_level_liters,
        "minimum_safe_stock_liters": tank.minimum_safe_level,
        "recommended_quantity": recommendation.recommended_quantity,
        "recommended_order_date": recommendation.recommended_order_date,
        "recommended_delivery_date": recommendation.recommended_delivery_date,
        "critical_stock_date": recommendation.critical_stock_date,
        "confidence_score": recommendation.confidence_score,
        "priority": recommendation.priority,
        "status": recommendation.status,
        "explanation": recommendation.explanation,
    }


@router.put("/tanks/{tank_id}", response_model=TankRead)
def update_tank(
    tank_id: int,
    payload: TankUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> object:
    return TankService(db).update(tank_id, payload)


@router.delete("/tanks/{tank_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_tank(
    tank_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    TankService(db).deactivate(tank_id)
