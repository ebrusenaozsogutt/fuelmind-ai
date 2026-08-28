"""Dashboard aggregation endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryRead
from app.services.dashboard_service import DashboardService
from app.simulation.manager import SimulationManager

router = APIRouter(prefix="/stations", tags=["dashboard"])


@router.get("/{station_id}/dashboard-summary", response_model=DashboardSummaryRead)
def dashboard_summary(
    station_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
):
    """Scope runtime-derived dashboard metrics to the manager-owned run."""

    manager: SimulationManager | None = getattr(
        request.app.state, "simulation_manager", None
    )
    run_id = manager.active_run_id_for_station(station_id) if manager else None
    return DashboardService(db).summary(station_id, simulation_run_id=run_id)
