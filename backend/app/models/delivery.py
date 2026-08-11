"""Fuel delivery database model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from app.models.tank import Tank


class Delivery(Base):
    """A fuel delivery received by a tank."""

    __tablename__ = "deliveries"
    __table_args__ = (
        CheckConstraint("quantity_liters > 0", name="ck_deliveries_quantity_positive"),
        CheckConstraint(
            "level_before >= 0", name="ck_deliveries_level_before_nonnegative"
        ),
        CheckConstraint(
            "level_after >= 0", name="ck_deliveries_level_after_nonnegative"
        ),
        CheckConstraint(
            "level_after >= level_before", name="ck_deliveries_level_increases"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tank_id: Mapped[int] = mapped_column(
        ForeignKey("tanks.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    simulation_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    simulation_delivery_id: Mapped[str | None] = mapped_column(
        String(150), unique=True, nullable=True
    )
    delivery_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    quantity_liters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    level_before: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    level_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Tank capacity is validated in the service layer.
    tank: Mapped[Tank] = relationship(back_populates="deliveries")
