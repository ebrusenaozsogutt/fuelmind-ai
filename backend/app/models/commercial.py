"""Commercial customer, fleet, card, and price database models."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import (
    CardLimitType,
    CardStatus,
    CustomerRequestStatus,
    CustomerType,
    DriverAssignmentStatus,
    PaymentType,
)

if TYPE_CHECKING:
    from app.models.fuel_type import FuelType
    from app.models.sale import Sale
    from app.models.station import Station
    from app.models.user import User


def _enum(enum_class: type) -> SqlEnum:
    """Build a PostgreSQL-compatible enum using its stable string values."""

    enum_name = "".join(
        f"_{character.lower()}" if character.isupper() else character
        for character in enum_class.__name__
    ).lstrip("_")

    return SqlEnum(
        enum_class,
        name=enum_name,
        native_enum=True,
        create_constraint=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


class Customer(Base):
    """Commercial account that owns fleets through the defined hierarchy."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("code", name="uq_customers_code"),
        CheckConstraint("discount_rate >= 0", name="ck_customers_discount_nonnegative"),
        CheckConstraint("discount_rate <= 100", name="ck_customers_discount_maximum"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    customer_type: Mapped[CustomerType] = mapped_column(
        _enum(CustomerType), nullable=False
    )
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tax_office: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    registration_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), nullable=False
    )
    request_status: Mapped[CustomerRequestStatus] = mapped_column(
        _enum(CustomerRequestStatus),
        default=CustomerRequestStatus.PENDING,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    authorized_persons: Mapped[list[CustomerAuthorizedPerson]] = relationship(
        back_populates="customer"
    )
    fleets: Mapped[list[Fleet]] = relationship(back_populates="customer")
    sales: Mapped[list[Sale]] = relationship(back_populates="customer")


class CustomerAuthorizedPerson(Base):
    """A person authorized to act for a commercial customer."""

    __tablename__ = "customer_authorized_persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    customer: Mapped[Customer] = relationship(back_populates="authorized_persons")


class Fleet(Base):
    """A customer-owned fleet."""

    __tablename__ = "fleets"
    __table_args__ = (UniqueConstraint("customer_id", "code", name="uq_fleets_customer_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_status: Mapped[CustomerRequestStatus] = mapped_column(
        _enum(CustomerRequestStatus),
        default=CustomerRequestStatus.PENDING,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    customer: Mapped[Customer] = relationship(back_populates="fleets")
    fleet_groups: Mapped[list[FleetGroup]] = relationship(back_populates="fleet")
    sales: Mapped[list[Sale]] = relationship(back_populates="fleet")


class FleetGroup(Base):
    """An operational grouping inside a fleet."""

    __tablename__ = "fleet_groups"
    __table_args__ = (UniqueConstraint("fleet_id", "code", name="uq_fleet_groups_fleet_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fleet_id: Mapped[int] = mapped_column(
        ForeignKey("fleets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    fleet: Mapped[Fleet] = relationship(back_populates="fleet_groups")
    vehicles: Mapped[list[Vehicle]] = relationship(back_populates="fleet_group")
    sales: Mapped[list[Sale]] = relationship(back_populates="fleet_group")


class Vehicle(Base):
    """A fleet vehicle; customer ownership is derived through its group."""

    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("plate", name="uq_vehicles_plate"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fleet_group_id: Mapped[int] = mapped_column(
        ForeignKey("fleet_groups.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    plate: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    fleet_group: Mapped[FleetGroup] = relationship(back_populates="vehicles")
    fuel_cards: Mapped[list[FuelCard]] = relationship(back_populates="vehicle")
    driver_assignments: Mapped[list[DriverVehicleAssignment]] = relationship(
        back_populates="vehicle"
    )
    sales: Mapped[list[Sale]] = relationship(back_populates="vehicle")


class Driver(Base):
    """A driver who may be assigned to vehicles over time."""

    __tablename__ = "drivers"
    __table_args__ = (UniqueConstraint("reference_code", name="uq_drivers_reference_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    reference_code: Mapped[str | None] = mapped_column(
        String(32), unique=True, index=True, nullable=True
    )
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    vehicle_assignments: Mapped[list[DriverVehicleAssignment]] = relationship(
        back_populates="driver"
    )
    sales: Mapped[list[Sale]] = relationship(back_populates="driver")


class DriverVehicleAssignment(Base):
    """A time-bounded driver assignment, retained for commercial history."""

    __tablename__ = "driver_vehicle_assignments"
    __table_args__ = (
        CheckConstraint(
            "assigned_until IS NULL OR assigned_until >= assigned_from",
            name="ck_driver_vehicle_assignments_date_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    assigned_from: Mapped[date] = mapped_column(Date, nullable=False)
    assigned_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[DriverAssignmentStatus] = mapped_column(
        _enum(DriverAssignmentStatus),
        default=DriverAssignmentStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    driver: Mapped[Driver] = relationship(back_populates="vehicle_assignments")
    vehicle: Mapped[Vehicle] = relationship(back_populates="driver_assignments")


class FuelCard(Base):
    """A technical card unit assigned to a vehicle."""

    __tablename__ = "fuel_cards"
    __table_args__ = (
        UniqueConstraint("card_code", name="uq_fuel_cards_card_code"),
        UniqueConstraint("unit_id", name="uq_fuel_cards_unit_id"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="ck_fuel_cards_validity_range",
        ),
        CheckConstraint(
            "prepaid_balance >= 0", name="ck_fuel_cards_prepaid_nonnegative"
        ),
        CheckConstraint(
            "credit_limit >= 0", name="ck_fuel_cards_credit_nonnegative"
        ),
        CheckConstraint("credit_used >= 0", name="ck_fuel_cards_credit_used_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    card_code: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    status: Mapped[CardStatus] = mapped_column(
        _enum(CardStatus), default=CardStatus.ACTIVE, nullable=False
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_type: Mapped[PaymentType] = mapped_column(
        _enum(PaymentType), nullable=False
    )
    prepaid_balance: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0"), nullable=False
    )
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0"), nullable=False
    )
    credit_used: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), default=Decimal("0"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    vehicle: Mapped[Vehicle] = relationship(back_populates="fuel_cards")
    limits: Mapped[list[FuelCardLimit]] = relationship(back_populates="fuel_card")
    allowed_stations: Mapped[list[FuelCardAllowedStation]] = relationship(
        back_populates="fuel_card"
    )
    allowed_fuel_types: Mapped[list[FuelCardAllowedFuelType]] = relationship(
        back_populates="fuel_card"
    )
    usage_windows: Mapped[list[FuelCardUsageWindow]] = relationship(
        back_populates="fuel_card"
    )
    sales: Mapped[list[Sale]] = relationship(back_populates="fuel_card")


class FuelCardLimit(Base):
    """One quantity limit period belonging to a fuel card."""

    __tablename__ = "fuel_card_limits"
    __table_args__ = (
        CheckConstraint(
            "quantity_limit_liters > 0", name="ck_fuel_card_limits_quantity_positive"
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="ck_fuel_card_limits_validity_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fuel_card_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_cards.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    limit_type: Mapped[CardLimitType] = mapped_column(_enum(CardLimitType), nullable=False)
    quantity_limit_liters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    fuel_card: Mapped[FuelCard] = relationship(back_populates="limits")


class FuelCardAllowedStation(Base):
    """An explicitly permitted station for a fuel card."""

    __tablename__ = "fuel_card_allowed_stations"
    __table_args__ = (
        UniqueConstraint(
            "fuel_card_id", "station_id", name="uq_fuel_card_allowed_stations_card_station"
        ),
        Index(
            "ix_fuel_card_allowed_stations_card_station",
            "fuel_card_id",
            "station_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fuel_card_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_cards.id", ondelete="RESTRICT"), nullable=False
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    fuel_card: Mapped[FuelCard] = relationship(back_populates="allowed_stations")
    station: Mapped[Station] = relationship(back_populates="allowed_fuel_cards")


class FuelCardAllowedFuelType(Base):
    """An explicitly permitted fuel product for a fuel card."""

    __tablename__ = "fuel_card_allowed_fuel_types"
    __table_args__ = (
        UniqueConstraint(
            "fuel_card_id", "fuel_type_id", name="uq_fuel_card_allowed_fuel_types_card_type"
        ),
        Index(
            "ix_fuel_card_allowed_fuel_types_card_type",
            "fuel_card_id",
            "fuel_type_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fuel_card_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_cards.id", ondelete="RESTRICT"), nullable=False
    )
    fuel_type_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_types.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    fuel_card: Mapped[FuelCard] = relationship(back_populates="allowed_fuel_types")
    fuel_type: Mapped[FuelType] = relationship(back_populates="allowed_fuel_cards")


class FuelCardUsageWindow(Base):
    """A same-day time window during which a fuel card is usable."""

    __tablename__ = "fuel_card_usage_windows"
    __table_args__ = (
        CheckConstraint(
            "day_of_week BETWEEN 0 AND 6", name="ck_fuel_card_usage_windows_day_range"
        ),
        CheckConstraint(
            "end_time > start_time", name="ck_fuel_card_usage_windows_time_range"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fuel_card_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_cards.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    fuel_card: Mapped[FuelCard] = relationship(back_populates="usage_windows")


class FuelPrice(Base):
    """An immutable price-history row for one station fuel type."""

    __tablename__ = "fuel_prices"
    __table_args__ = (
        Index(
            "ix_fuel_prices_station_type_effective_from",
            "station_id",
            "fuel_type_id",
            "effective_from",
        ),
        CheckConstraint("unit_price > 0", name="ck_fuel_prices_unit_price_positive"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="ck_fuel_prices_effectivity_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    fuel_type_id: Mapped[int] = mapped_column(
        ForeignKey("fuel_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    station: Mapped[Station] = relationship(back_populates="fuel_prices")
    fuel_type: Mapped[FuelType] = relationship(back_populates="fuel_prices")
    created_by_user: Mapped[User | None] = relationship(back_populates="fuel_prices")
