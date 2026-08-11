"""Sensor reading database model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import AnomalyType, SourceType

if TYPE_CHECKING:
    from app.models.pump import Pump
    from app.models.station import Station
    from app.models.tank import Tank


class SensorReading(Base):
    """A station sensor observation associated with a tank, pump, or both."""

    __tablename__ = "sensor_readings"
    __table_args__ = (
        Index(
            "ix_sensor_readings_station_timestamp", "station_id", "reading_timestamp"
        ),
        CheckConstraint(
            "tank_id IS NOT NULL OR pump_id IS NOT NULL",
            name="ck_sensor_readings_target_present",
        ),
        CheckConstraint(
            "tank_level IS NULL OR tank_level >= 0",
            name="ck_sensor_readings_tank_level_nonnegative",
        ),
        CheckConstraint(
            "water_level IS NULL OR water_level >= 0",
            name="ck_sensor_readings_water_level_nonnegative",
        ),
        CheckConstraint(
            "flow_rate IS NULL OR flow_rate >= 0",
            name="ck_sensor_readings_flow_rate_nonnegative",
        ),
        CheckConstraint(
            "pressure IS NULL OR pressure >= 0",
            name="ck_sensor_readings_pressure_nonnegative",
        ),
        CheckConstraint(
            "motor_current IS NULL OR motor_current >= 0",
            name="ck_sensor_readings_motor_current_nonnegative",
        ),
        CheckConstraint(
            "working_duration IS NULL OR working_duration >= 0",
            name="ck_sensor_readings_working_duration_nonnegative",
        ),
        CheckConstraint(
            "error_count >= 0", name="ck_sensor_readings_error_count_nonnegative"
        ),
        CheckConstraint(
            "data_quality_score BETWEEN 0 AND 100",
            name="ck_sensor_readings_quality_score_range",
        ),
        CheckConstraint(
            "anomaly_score IS NULL OR anomaly_score BETWEEN 0 AND 100",
            name="ck_sensor_readings_anomaly_score_range",
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
    simulation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reading_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    tank_level: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    true_tank_level: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    water_level: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    flow_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    pressure: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    motor_current: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    pump_temperature: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    working_duration: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    data_quality_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    quality_flags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    anomaly_type: Mapped[AnomalyType | None] = mapped_column(
        SqlEnum(
            AnomalyType,
            name="anomaly_type",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=True,
    )
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

    station: Mapped[Station] = relationship(back_populates="sensor_readings")
    tank: Mapped[Tank | None] = relationship(back_populates="sensor_readings")
    pump: Mapped[Pump | None] = relationship(back_populates="sensor_readings")
