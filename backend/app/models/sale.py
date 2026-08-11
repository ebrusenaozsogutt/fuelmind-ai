"""Fuel sale database model."""

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
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import AnomalyType

if TYPE_CHECKING:
    from app.models.fuel_type import FuelType
    from app.models.pump import Pump
    from app.models.station import Station
    from app.models.tank import Tank


class Sale(Base):
    """A completed fuel sale recorded by a pump."""

    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("quantity_liters > 0", name="ck_sales_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_sales_unit_price_nonnegative"),
        CheckConstraint("total_amount >= 0", name="ck_sales_total_amount_nonnegative"),
        CheckConstraint("duration_seconds >= 0", name="ck_sales_duration_nonnegative"),
        CheckConstraint("level_before >= 0", name="ck_sales_level_before_nonnegative"),
        CheckConstraint("level_after >= 0", name="ck_sales_level_after_nonnegative"),
        CheckConstraint(
            "anomaly_score IS NULL OR anomaly_score BETWEEN 0 AND 100",
            name="ck_sales_anomaly_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    tank_id: Mapped[int] = mapped_column(
        ForeignKey("tanks.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    pump_id: Mapped[int] = mapped_column(
        ForeignKey("pumps.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    simulation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    simulation_sale_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )
    fuel_type_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    sale_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    quantity_liters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    level_before: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    level_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Station, tank, pump, and fuel-type compatibility is validated in services.
    station: Mapped[Station] = relationship(back_populates="sales")
    tank: Mapped[Tank] = relationship(back_populates="sales")
    pump: Mapped[Pump] = relationship(back_populates="sales")
    fuel_type: Mapped[FuelType] = relationship(back_populates="sales")
