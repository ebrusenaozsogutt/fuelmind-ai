"""Historical tank-probe measurement database model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import SourceType

if TYPE_CHECKING:
    from app.models.tank import Tank
    from app.models.tank_probe import TankProbe


class ProbeReading(Base):
    """One historical observation received from or generated for a tank probe."""

    __tablename__ = "probe_readings"
    __table_args__ = (
        Index("ix_probe_readings_probe_timestamp", "probe_id", "reading_timestamp"),
        Index("ix_probe_readings_tank_timestamp", "tank_id", "reading_timestamp"),
        CheckConstraint(
            "fuel_height_mm IS NULL OR fuel_height_mm >= 0",
            name="ck_probe_readings_fuel_height_nonnegative",
        ),
        CheckConstraint(
            "fuel_volume_liters IS NULL OR fuel_volume_liters >= 0",
            name="ck_probe_readings_fuel_volume_nonnegative",
        ),
        CheckConstraint(
            "water_height_mm IS NULL OR water_height_mm >= 0",
            name="ck_probe_readings_water_height_nonnegative",
        ),
        CheckConstraint(
            "water_volume_liters IS NULL OR water_volume_liters >= 0",
            name="ck_probe_readings_water_volume_nonnegative",
        ),
        CheckConstraint(
            "data_quality_score BETWEEN 0 AND 100",
            name="ck_probe_readings_quality_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    probe_id: Mapped[int] = mapped_column(
        ForeignKey("tank_probes.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    tank_id: Mapped[int] = mapped_column(
        ForeignKey("tanks.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    simulation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reading_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fuel_height_mm: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    fuel_volume_liters: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    water_height_mm: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    water_volume_liters: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    temperature_celsius: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    data_quality_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    quality_flags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        SqlEnum(
            SourceType,
            name="source_type",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=SourceType.MANUAL,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    probe: Mapped[TankProbe] = relationship(back_populates="readings")
    tank: Mapped[Tank] = relationship(back_populates="probe_readings")
