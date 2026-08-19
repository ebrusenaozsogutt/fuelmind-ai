from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.operations import Attendant, AttendantShiftAssignment, Shift
from app.models.station import Station
from app.models.user import User
from app.schemas.operations import (
    AttendantCreate,
    AttendantRead,
    AttendantShiftAssignmentCreate,
    AttendantShiftAssignmentRead,
    AttendantShiftAssignmentUpdate,
    AttendantUpdate,
    ShiftCreate,
    ShiftRead,
    ShiftUpdate,
)
from app.services.operations_service import OperationsService

router = APIRouter(tags=["Operations"])


def _get(db, cls, id):
    value = db.get(cls, id)
    if value is None:
        raise NotFoundError(f"{cls.__name__} not found.")
    return value


def _commit(db, entity):
    try:
        db.commit()
        db.refresh(entity)
        return entity
    except Exception:
        db.rollback()
        raise


@router.get("/attendants", response_model=list[AttendantRead])
def attendants(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    station_id: int | None = None,
):
    q = select(Attendant)
    q = q.where(Attendant.station_id == station_id) if station_id else q
    return list(db.scalars(q.order_by(Attendant.code)))


@router.post(
    "/attendants", response_model=AttendantRead, status_code=status.HTTP_201_CREATED
)
def add_attendant(
    p: AttendantCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
):
    _get(db, Station, p.station_id)
    if db.scalar(
        select(Attendant).where(
            Attendant.station_id == p.station_id, Attendant.code == p.code
        )
    ) or db.scalar(
        select(Attendant).where(Attendant.employee_number == p.employee_number)
    ):
        raise ConflictError("Attendant code or employee number already exists.")
    entity = Attendant(**p.model_dump())
    db.add(entity)
    return _commit(db, entity)


@router.get("/attendants/{id}", response_model=AttendantRead)
def attendant(
    id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
):
    return _get(db, Attendant, id)


@router.put("/attendants/{id}", response_model=AttendantRead)
def update_attendant(
    id: int,
    p: AttendantUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
):
    return OperationsService(db).update_attendant(
        id,
        p.model_dump(exclude_unset=True),
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
    )


@router.delete("/attendants/{id}", status_code=204)
def deactivate_attendant(
    id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
):
    OperationsService(db).deactivate_attendant(
        id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
    )


@router.get("/shifts", response_model=list[ShiftRead])
def shifts(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    station_id: int | None = None,
):
    q = select(Shift)
    q = q.where(Shift.station_id == station_id) if station_id else q
    return list(db.scalars(q.order_by(Shift.code)))


@router.post("/shifts", response_model=ShiftRead, status_code=201)
def add_shift(
    p: ShiftCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
):
    _get(db, Station, p.station_id)
    entity = Shift(**p.model_dump())
    db.add(entity)
    return _commit(db, entity)


@router.get("/shifts/{id}", response_model=ShiftRead)
def shift(
    id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
):
    return _get(db, Shift, id)


@router.put("/shifts/{id}", response_model=ShiftRead)
def update_shift(
    id: int,
    p: ShiftUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
):
    return OperationsService(db).update_shift(
        id,
        p.model_dump(exclude_unset=True),
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
    )


@router.delete("/shifts/{id}", status_code=204)
def deactivate_shift(
    id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
):
    OperationsService(db).deactivate_shift(
        id,
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None),
    )


@router.post(
    "/attendant-shift-assignments",
    response_model=AttendantShiftAssignmentRead,
    status_code=201,
)
def assign(
    p: AttendantShiftAssignmentCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
):
    attendant = _get(db, Attendant, p.attendant_id)
    shift = _get(db, Shift, p.shift_id)
    if attendant.station_id != shift.station_id:
        raise BusinessRuleError("Attendant and shift must belong to the same station.")
    entity = AttendantShiftAssignment(
        attendant_id=attendant.id,
        shift_id=shift.id,
        station_id=attendant.station_id,
        is_active=p.is_active,
    )
    db.add(entity)
    return _commit(db, entity)


@router.get("/attendant-shift-assignments", response_model=list[AttendantShiftAssignmentRead])
def assignments(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
    station_id: int | None = None,
    attendant_id: int | None = None,
    shift_id: int | None = None,
    is_active: bool | None = None,
):
    query = select(AttendantShiftAssignment)
    for column, value in ((AttendantShiftAssignment.station_id, station_id), (AttendantShiftAssignment.attendant_id, attendant_id), (AttendantShiftAssignment.shift_id, shift_id), (AttendantShiftAssignment.is_active, is_active)):
        if value is not None:
            query = query.where(column == value)
    return list(db.scalars(query.order_by(AttendantShiftAssignment.id)))


@router.patch("/attendant-shift-assignments/{id}", response_model=AttendantShiftAssignmentRead)
def update_assignment(
    id: int,
    payload: AttendantShiftAssignmentUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
):
    entity = _get(db, AttendantShiftAssignment, id)
    entity.is_active = payload.is_active
    return _commit(db, entity)
