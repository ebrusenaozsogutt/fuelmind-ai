"""Durable, explicit equipment fault records kept separate from alarms."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import FaultCode, FaultStatus, FaultTargetType, FaultType

if TYPE_CHECKING:
    from app.models.alarm import Alarm
    from app.models.station import Station
    from app.models.user import User


def _enum(enum_class: type) -> SqlEnum:
    return SqlEnum(
        enum_class,
        name="".join(
            f"_{character.lower()}" if character.isupper() else character
            for character in enum_class.__name__
        ).lstrip("_"),
        native_enum=True,
        create_constraint=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


class Fault(Base):
    """A lifecycle-managed fault record for one station-owned target."""

    __tablename__ = "faults"
    __table_args__ = (
        UniqueConstraint("alarm_id", name="uq_faults_alarm_id"),
        Index("ix_faults_station_detected_at", "station_id", "detected_at"),
        Index("ix_faults_fault_code", "fault_code"),
        Index("ix_faults_status", "status"),
        Index("ix_faults_alarm_id", "alarm_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False)
    alarm_id: Mapped[int | None] = mapped_column(ForeignKey("alarms.id", ondelete="RESTRICT"), nullable=True)
    target_type: Mapped[FaultTargetType] = mapped_column(_enum(FaultTargetType), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    fault_type: Mapped[FaultType] = mapped_column(_enum(FaultType), nullable=False)
    fault_code: Mapped[FaultCode] = mapped_column(_enum(FaultCode), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[FaultStatus] = mapped_column(_enum(FaultStatus), default=FaultStatus.OPEN, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    station: Mapped[Station] = relationship()
    alarm: Mapped[Alarm | None] = relationship(back_populates="faults")
    resolver_user: Mapped[User | None] = relationship(back_populates="resolved_faults")
