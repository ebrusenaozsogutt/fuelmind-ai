"""Deterministic operational context selection for simulated sales."""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Protocol, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operations import Attendant, AttendantShiftAssignment, Shift


T = TypeVar("T")


class _ChoiceSource(Protocol):
    def choice(self, sequence: Sequence[T]) -> T: ...


@dataclass(frozen=True)
class OperationsSelection:
    """The attendant and shift fixed when a simulated sale starts."""

    attendant_id: int
    attendant_name: str
    shift_id: int
    shift_name: str


class OperationsSelectionService:
    """Resolve a station's active assigned attendant from virtual simulation time."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def select_for_sale(
        self,
        *,
        station_id: int,
        simulation_time: datetime,
        random_source: _ChoiceSource,
    ) -> OperationsSelection | None:
        """Return one active assignment, or ``None`` for legacy station fallback."""

        if simulation_time.tzinfo is None or simulation_time.utcoffset() is None:
            raise ValueError("simulation_time must include a timezone.")
        local_time = simulation_time.timetz().replace(tzinfo=None)
        assignments = list(
            self.db.execute(
                select(Attendant, Shift)
                .join(
                    AttendantShiftAssignment,
                    AttendantShiftAssignment.attendant_id == Attendant.id,
                )
                .join(Shift, AttendantShiftAssignment.shift_id == Shift.id)
                .where(
                    AttendantShiftAssignment.station_id == station_id,
                    AttendantShiftAssignment.is_active.is_(True),
                    Attendant.station_id == station_id,
                    Attendant.is_active.is_(True),
                    Shift.station_id == station_id,
                    Shift.is_active.is_(True),
                )
                .order_by(Shift.id, Attendant.id)
            ).all()
        )
        candidates = [
            (attendant, shift)
            for attendant, shift in assignments
            if self._is_active_shift(shift.start_time, shift.end_time, local_time)
        ]
        if not candidates:
            return None
        attendant, shift = random_source.choice(candidates)
        return OperationsSelection(
            attendant_id=attendant.id,
            attendant_name=attendant.full_name,
            shift_id=shift.id,
            shift_name=shift.name,
        )

    @staticmethod
    def _is_active_shift(start_time: time, end_time: time, moment: time) -> bool:
        """Treat end time as exclusive and handle intervals spanning midnight."""

        if start_time == end_time:
            return False
        if start_time < end_time:
            return start_time <= moment < end_time
        return moment >= start_time or moment < end_time
