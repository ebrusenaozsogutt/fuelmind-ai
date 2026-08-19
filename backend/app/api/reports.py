"""Read-only persisted-data reporting endpoints."""

from typing import Annotated, Any
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app.api.dependencies import require_operator_or_admin
from app.database import get_db
from app.models.user import User
from app.schemas.report import ReportFilters
from app.services.report_service import ReportService
from app.services.report_export_service import REPORTS, ReportExportService
from app.utils.datetime_utils import utc_now

router = APIRouter(prefix="/reports", tags=["Reports"])

def _service(db: Session) -> ReportService: return ReportService(db)
def _page(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)) -> tuple[int, int]: return skip, limit

@router.get("/end-of-day")
def end_of_day(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()]) -> dict[str, Any]: return _service(db).end_of_day(filters)
@router.get("/sales")
def sales(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()], page: Annotated[tuple[int, int], Depends(_page)]) -> list[dict[str, Any]]: return _service(db).sales(filters, *page)
@router.get("/attendants")
def attendants(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()]) -> list[dict[str, Any]]: return _service(db).attendants(filters)
@router.get("/deliveries")
def deliveries(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()], page: Annotated[tuple[int, int], Depends(_page)]) -> list[dict[str, Any]]: return _service(db).deliveries(filters, *page)
@router.get("/tank-measurements")
def tank_measurements(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()], page: Annotated[tuple[int, int], Depends(_page)]) -> list[dict[str, Any]]: return _service(db).tank_measurements(filters, *page)
@router.get("/price-changes")
def price_changes(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()], page: Annotated[tuple[int, int], Depends(_page)]) -> list[dict[str, Any]]: return _service(db).price_changes(filters, *page)
@router.get("/faults")
def faults(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()], page: Annotated[tuple[int, int], Depends(_page)]) -> list[dict[str, Any]]: return _service(db).faults(filters, *page)
@router.get("/customer-sales")
def customer_sales(db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()]) -> list[dict[str, Any]]: return _service(db).customer_sales(filters)

@router.get("/{report_type}/export/csv")
def export_csv(report_type: str, db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()]) -> Response:
    if report_type not in REPORTS:
        return Response(status_code=404)
    body = ReportExportService(_service(db)).csv(report_type, filters)
    return Response(body, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="fuelmind_{report_type}_{utc_now().date()}.csv"'})

@router.get("/{report_type}/export/pdf")
def export_pdf(report_type: str, db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)], filters: Annotated[ReportFilters, Depends()]) -> Response:
    if report_type not in REPORTS:
        return Response(status_code=404)
    body = ReportExportService(_service(db)).pdf(report_type, filters)
    return Response(body, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="fuelmind_{report_type}_{utc_now().date()}.pdf"'})
