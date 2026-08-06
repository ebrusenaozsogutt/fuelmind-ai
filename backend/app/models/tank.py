"""Fuel tank database model."""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import SensorStatus

if TYPE_CHECKING:
    from app.models.alarm import Alarm
    from app.models.delivery import Delivery
    from app.models.fuel_type import FuelType
    from app.models.order_recommendation import OrderRecommendation
    from app.models.pump import Pump
    from app.models.sale import Sale
    from app.models.sensor_reading import SensorReading
    from app.models.station import Station


class Tank(Base):
    """A fuel storage tank assigned to one station and fuel type."""

    __tablename__ = "tanks"
    __table_args__ = (
        UniqueConstraint("station_id", "code", name="uq_tanks_station_code"),
        CheckConstraint("capacity_liters > 0", name="ck_tanks_capacity_positive"),
        CheckConstraint(
            "current_level_liters >= 0", name="ck_tanks_current_level_nonnegative"
        ),
        CheckConstraint(
            "minimum_safe_level >= 0", name="ck_tanks_min_safe_nonnegative"
        ),
        CheckConstraint("critical_level >= 0", name="ck_tanks_critical_nonnegative"),
        CheckConstraint(
            "current_level_liters <= capacity_liters",
            name="ck_tanks_current_level_within_capacity",
        ),
        CheckConstraint(
            "minimum_safe_level <= capacity_liters",
            name="ck_tanks_min_safe_within_capacity",
        ),
        CheckConstraint(
            "critical_level <= capacity_liters",
            name="ck_tanks_critical_within_capacity",
        ),
        CheckConstraint("water_level >= 0", name="ck_tanks_water_level_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    fuel_type_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    capacity_liters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    current_level_liters: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    minimum_safe_level: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    critical_level: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    water_level: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), nullable=False
    )
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    sensor_status: Mapped[SensorStatus] = mapped_column(
        SqlEnum(
            SensorStatus,
            name="sensor_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=SensorStatus.ACTIVE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    station: Mapped[Station] = relationship(back_populates="tanks")
    fuel_type: Mapped[FuelType] = relationship(back_populates="tanks")
    pumps: Mapped[list[Pump]] = relationship(back_populates="tank")
    sales: Mapped[list[Sale]] = relationship(back_populates="tank")
    sensor_readings: Mapped[list[SensorReading]] = relationship(back_populates="tank")
    deliveries: Mapped[list[Delivery]] = relationship(back_populates="tank")
    alarms: Mapped[list[Alarm]] = relationship(back_populates="tank")
    order_recommendations: Mapped[list[OrderRecommendation]] = relationship(
        back_populates="tank"
    )
