"""Demand forecast database model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.fuel_type import FuelType
    from app.models.station import Station


class Forecast(Base):
    """A model-generated fuel demand forecast."""

    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint(
            "station_id",
            "fuel_type_id",
            "forecast_date",
            "model_version",
            name="uq_forecasts_station_fuel_date_model",
        ),
        CheckConstraint(
            "predicted_demand >= 0", name="ck_forecasts_predicted_demand_nonnegative"
        ),
        CheckConstraint(
            "lower_bound >= 0", name="ck_forecasts_lower_bound_nonnegative"
        ),
        CheckConstraint(
            "upper_bound >= 0", name="ck_forecasts_upper_bound_nonnegative"
        ),
        CheckConstraint(
            "lower_bound <= predicted_demand",
            name="ck_forecasts_lower_within_prediction",
        ),
        CheckConstraint(
            "predicted_demand <= upper_bound",
            name="ck_forecasts_prediction_within_upper",
        ),
        CheckConstraint(
            "confidence_score BETWEEN 0 AND 100",
            name="ck_forecasts_confidence_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    fuel_type_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    forecast_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    predicted_demand: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    lower_bound: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    upper_bound: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    station: Mapped[Station] = relationship(back_populates="forecasts")
    fuel_type: Mapped[FuelType] = relationship(back_populates="forecasts")
