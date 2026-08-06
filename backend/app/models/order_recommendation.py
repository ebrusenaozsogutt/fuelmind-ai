"""Fuel order recommendation database model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import RecommendationPriority, RecommendationStatus

if TYPE_CHECKING:
    from app.models.station import Station
    from app.models.tank import Tank


class OrderRecommendation(Base):
    """A recommended fuel replenishment order for a tank."""

    __tablename__ = "order_recommendations"
    __table_args__ = (
        CheckConstraint(
            "recommended_quantity >= 0",
            name="ck_order_recommendations_quantity_nonnegative",
        ),
        CheckConstraint(
            "confidence_score BETWEEN 0 AND 100",
            name="ck_order_recommendations_confidence_score_range",
        ),
        CheckConstraint(
            "recommended_delivery_date >= recommended_order_date",
            name="ck_order_recommendations_delivery_after_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    tank_id: Mapped[int] = mapped_column(
        ForeignKey("tanks.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    recommended_order_date: Mapped[date] = mapped_column(Date, nullable=False)
    recommended_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    recommended_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    critical_stock_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    priority: Mapped[RecommendationPriority] = mapped_column(
        SqlEnum(
            RecommendationPriority,
            name="recommendation_priority",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=RecommendationPriority.MEDIUM,
        nullable=False,
    )
    status: Mapped[RecommendationStatus] = mapped_column(
        SqlEnum(
            RecommendationStatus,
            name="recommendation_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=RecommendationStatus.NEW,
        nullable=False,
    )
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    station: Mapped[Station] = relationship(back_populates="order_recommendations")
    tank: Mapped[Tank] = relationship(back_populates="order_recommendations")
