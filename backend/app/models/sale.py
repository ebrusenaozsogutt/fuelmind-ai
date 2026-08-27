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
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import AnomalyType, PaymentType, SaleStatus

if TYPE_CHECKING:
    from app.models.commercial import (
        Customer,
        Driver,
        Fleet,
        FleetGroup,
        FuelCard,
        Vehicle,
    )
    from app.models.fuel_type import FuelType
    from app.models.nozzle import Nozzle
    from app.models.pump import Pump
    from app.models.station import Station
    from app.models.operations import Attendant, Shift
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
        CheckConstraint(
            "start_totalizer_liters IS NULL OR start_totalizer_liters >= 0",
            name="ck_sales_start_totalizer_nonnegative",
        ),
        CheckConstraint(
            "end_totalizer_liters IS NULL OR end_totalizer_liters >= 0",
            name="ck_sales_end_totalizer_nonnegative",
        ),
        CheckConstraint(
            "start_totalizer_liters IS NULL OR end_totalizer_liters IS NULL "
            "OR end_totalizer_liters >= start_totalizer_liters",
            name="ck_sales_totalizer_order",
        ),
        CheckConstraint(
            "start_totalizer_liters IS NULL OR end_totalizer_liters IS NULL "
            "OR ABS((end_totalizer_liters - start_totalizer_liters) - quantity_liters) <= 0.001",
            name="ck_sales_totalizer_quantity_matches",
        ),
        CheckConstraint(
            "discount_rate IS NULL OR discount_rate >= 0",
            name="ck_sales_discount_nonnegative",
        ),
        CheckConstraint(
            "discount_rate IS NULL OR discount_rate <= 100",
            name="ck_sales_discount_maximum",
        ),
        Index("ix_sales_customer_id_timestamp", "customer_id", "sale_timestamp"),
        Index("ix_sales_vehicle_id_timestamp", "vehicle_id", "sale_timestamp"),
        Index("ix_sales_fuel_card_id_timestamp", "fuel_card_id", "sale_timestamp"),
        Index("ix_sales_nozzle_id_timestamp", "nozzle_id", "sale_timestamp"),
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
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    fleet_id: Mapped[int | None] = mapped_column(
        ForeignKey("fleets.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    fleet_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("fleet_groups.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    fuel_card_id: Mapped[int | None] = mapped_column(
        ForeignKey("fuel_cards.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    nozzle_id: Mapped[int | None] = mapped_column(
        ForeignKey("nozzles.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    attendant_id: Mapped[int | None] = mapped_column(ForeignKey("attendants.id", ondelete="RESTRICT"), index=True, nullable=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id", ondelete="RESTRICT"), index=True, nullable=True)
    sale_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    quantity_liters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    start_totalizer_liters: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    end_totalizer_liters: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    list_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    discount_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sale_status: Mapped[SaleStatus] = mapped_column(
        SqlEnum(
            SaleStatus,
            name="sale_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=SaleStatus.COMPLETED,
        nullable=False,
    )
    authorization_failure_code: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    payment_type: Mapped[PaymentType | None] = mapped_column(
        SqlEnum(
            PaymentType,
            name="payment_type",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=True,
    )
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
    customer: Mapped[Customer | None] = relationship(back_populates="sales")
    fleet: Mapped[Fleet | None] = relationship(back_populates="sales")
    fleet_group: Mapped[FleetGroup | None] = relationship(back_populates="sales")
    vehicle: Mapped[Vehicle | None] = relationship(back_populates="sales")
    driver: Mapped[Driver | None] = relationship(back_populates="sales")
    fuel_card: Mapped[FuelCard | None] = relationship(back_populates="sales")
    nozzle: Mapped[Nozzle | None] = relationship(back_populates="sales")
    attendant: Mapped[Attendant | None] = relationship(back_populates="sales")
    shift: Mapped[Shift | None] = relationship(back_populates="sales")

    @property
    def attendant_name(self) -> str | None:
        """Expose an additive attendant display value in sale API responses."""

        return self.attendant.full_name if self.attendant is not None else None

    @property
    def shift_name(self) -> str | None:
        """Expose an additive shift display value in sale API responses."""

        return self.shift.name if self.shift is not None else None
