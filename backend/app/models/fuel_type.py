"""Fuel type database model."""

# veritabanındaki yakıt türlerini temsil eden bir SQLAlchemy modelini tanımlar.
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.forecast import Forecast
    from app.models.sale import Sale
    from app.models.tank import Tank


class FuelType(Base):
    """A fuel product that can be stored in tanks."""

    __tablename__ = "fuel_types"
    __table_args__ = (UniqueConstraint("code", name="uq_fuel_types_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    unit: Mapped[str] = mapped_column(String(16), default="LITER", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tanks: Mapped[list[Tank]] = relationship(back_populates="fuel_type")
    sales: Mapped[list[Sale]] = relationship(back_populates="fuel_type")
    forecasts: Mapped[list[Forecast]] = relationship(back_populates="fuel_type")
