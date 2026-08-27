"""Alarm database model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.enums import AlarmSeverity, AlarmStatus

if TYPE_CHECKING:
    from app.models.fault import Fault
    from app.models.pump import Pump
    from app.models.station import Station
    from app.models.tank import Tank
    from app.models.user import User


class Alarm(Base):
    """An operational alarm for a station, tank, or pump."""

    __tablename__ = "alarms"
    __table_args__ = (
        CheckConstraint(
            "anomaly_score IS NULL OR anomaly_score BETWEEN 0 AND 100",
            name="ck_alarms_anomaly_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    tank_id: Mapped[int | None] = mapped_column(
        ForeignKey("tanks.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    pump_id: Mapped[int | None] = mapped_column(
        ForeignKey("pumps.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    target_type: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    alarm_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    severity: Mapped[AlarmSeverity] = mapped_column(
        SqlEnum(
            AlarmSeverity,
            name="alarm_severity",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    probable_causes: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, nullable=True
    )
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decision_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    anomaly_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_outlier: Mapped[bool | None] = mapped_column(nullable=True)
    triggered_rules_json: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    findings_json: Mapped[list[dict[str, object] | str] | None] = mapped_column(JSONB, nullable=True)
    recommended_checks_json: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    data_quality_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AlarmStatus] = mapped_column(
        SqlEnum(
            AlarmStatus,
            name="alarm_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=AlarmStatus.NEW,
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    station: Mapped[Station] = relationship(back_populates="alarms")
    tank: Mapped[Tank | None] = relationship(back_populates="alarms")
    pump: Mapped[Pump | None] = relationship(back_populates="alarms")
    resolver_user: Mapped[User | None] = relationship(back_populates="resolved_alarms")
    faults: Mapped[list[Fault]] = relationship(back_populates="alarm")
