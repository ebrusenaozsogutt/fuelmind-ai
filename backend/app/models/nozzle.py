"""Pump nozzle database model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import NozzleStatus

if TYPE_CHECKING:
    from app.models.fuel_type import FuelType
    from app.models.pump import Pump
    from app.models.sale import Sale


class Nozzle(Base):
    """A fuel-specific dispensing nozzle attached to a pump."""

    __tablename__ = "nozzles"
    __table_args__ = (
        UniqueConstraint("pump_id", "nozzle_number", name="uq_nozzles_pump_number"),
        CheckConstraint(
            "totalizer_liters >= 0", name="ck_nozzles_totalizer_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pump_id: Mapped[int] = mapped_column(
        ForeignKey("pumps.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    fuel_type_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    nozzle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[NozzleStatus] = mapped_column(
        SqlEnum(
            NozzleStatus,
            name="nozzle_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=NozzleStatus.AVAILABLE,
        nullable=False,
    )
    totalizer_liters: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    pump: Mapped[Pump] = relationship(back_populates="nozzles")
    fuel_type: Mapped[FuelType] = relationship(back_populates="nozzles")
    sales: Mapped[list[Sale]] = relationship(back_populates="nozzle")

    @property
    def pump_code(self) -> str:
        """Expose a compact pump label for management API responses."""

        return self.pump.code

    @property
    def fuel_type_code(self) -> str:
        """Expose a compact fuel-type code for management API responses."""

        return self.fuel_type.code

    @property
    def fuel_type_name(self) -> str:
        """Expose a compact fuel-type name for management API responses."""

        return self.fuel_type.name
