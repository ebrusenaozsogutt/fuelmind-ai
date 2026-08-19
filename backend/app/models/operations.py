"""Station operational personnel and shift records."""

from datetime import datetime, time
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.sale import Sale


class Attendant(Base):
    __tablename__ = "attendants"
    __table_args__ = (
        UniqueConstraint("station_id", "code", name="uq_attendants_station_code"),
        UniqueConstraint("employee_number", name="uq_attendants_employee_number"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    employee_number: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    assignments: Mapped[list["AttendantShiftAssignment"]] = relationship(
        back_populates="attendant"
    )
    sales: Mapped[list["Sale"]] = relationship(back_populates="attendant")


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        UniqueConstraint("station_id", "code", name="uq_shifts_station_code"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    assignments: Mapped[list["AttendantShiftAssignment"]] = relationship(
        back_populates="shift"
    )
    sales: Mapped[list["Sale"]] = relationship(back_populates="shift")


class AttendantShiftAssignment(Base):
    __tablename__ = "attendant_shift_assignments"
    __table_args__ = (
        UniqueConstraint(
            "attendant_id", "shift_id", name="uq_attendant_shift_assignment"
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attendant_id: Mapped[int] = mapped_column(
        ForeignKey("attendants.id", ondelete="RESTRICT"), index=True
    )
    shift_id: Mapped[int] = mapped_column(
        ForeignKey("shifts.id", ondelete="RESTRICT"), index=True
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    attendant: Mapped[Attendant] = relationship(back_populates="assignments")
    shift: Mapped[Shift] = relationship(back_populates="assignments")
