"""Dashboard aggregation endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryRead
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/stations", tags=["dashboard"])


@router.get("/{station_id}/dashboard-summary", response_model=DashboardSummaryRead)
def dashboard_summary(station_id: int, db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)]):
    return DashboardService(db).summary(station_id)
