"""Fuel station database model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.alarm import Alarm
    from app.models.forecast import Forecast
    from app.models.order_recommendation import OrderRecommendation
    from app.models.pump import Pump
    from app.models.sale import Sale
    from app.models.sensor_reading import SensorReading
    from app.models.tank import Tank


class Station(Base):
    """A fuel station that owns tanks and pumps."""

    __tablename__ = "stations"
    __table_args__ = (UniqueConstraint("code", name="uq_stations_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    district: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    tanks: Mapped[list[Tank]] = relationship(
        back_populates="station", cascade="save-update, merge"
    )
    pumps: Mapped[list[Pump]] = relationship(
        back_populates="station", cascade="save-update, merge"
    )
    sales: Mapped[list[Sale]] = relationship(back_populates="station")
    sensor_readings: Mapped[list[SensorReading]] = relationship(
        back_populates="station"
    )
    alarms: Mapped[list[Alarm]] = relationship(back_populates="station")
    forecasts: Mapped[list[Forecast]] = relationship(back_populates="station")
    order_recommendations: Mapped[list[OrderRecommendation]] = relationship(
        back_populates="station"
    )
