"""Fuel pump database model."""

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
from app.utils.enums import PumpStatus

if TYPE_CHECKING:
    from app.models.alarm import Alarm
    from app.models.communication_port import CommunicationPort
    from app.models.nozzle import Nozzle
    from app.models.sale import Sale
    from app.models.sensor_reading import SensorReading
    from app.models.station import Station
    from app.models.tank import Tank


class Pump(Base):
    """A dispensing pump supplied by a tank at the same station."""

    __tablename__ = "pumps"
    __table_args__ = (
        UniqueConstraint("station_id", "code", name="uq_pumps_station_code"),
        CheckConstraint("nominal_flow_rate > 0", name="ck_pumps_nominal_flow_positive"),
        CheckConstraint("minimum_flow_rate >= 0", name="ck_pumps_min_flow_nonnegative"),
        CheckConstraint(
            "minimum_flow_rate <= nominal_flow_rate",
            name="ck_pumps_min_flow_within_nominal",
        ),
        CheckConstraint(
            "maximum_motor_current > 0", name="ck_pumps_motor_current_positive"
        ),
        CheckConstraint("maximum_pressure > 0", name="ck_pumps_pressure_positive"),
        CheckConstraint(
            "total_working_hours >= 0", name="ck_pumps_working_hours_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    tank_id: Mapped[int] = mapped_column(
        ForeignKey("tanks.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    communication_port_id: Mapped[int | None] = mapped_column(
        ForeignKey("communication_ports.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    device_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[PumpStatus] = mapped_column(
        SqlEnum(
            PumpStatus,
            name="pump_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=PumpStatus.IDLE,
        nullable=False,
    )
    nominal_flow_rate: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    minimum_flow_rate: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    maximum_motor_current: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    maximum_pressure: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    last_maintenance_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_working_hours: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # This is validated in the service layer: foreign keys alone cannot ensure
    # that this pump and its assigned tank belong to the same station.
    station: Mapped[Station] = relationship(back_populates="pumps")
    tank: Mapped[Tank] = relationship(back_populates="pumps")
    communication_port: Mapped[CommunicationPort | None] = relationship(
        back_populates="pumps"
    )
    sales: Mapped[list[Sale]] = relationship(back_populates="pump")
    sensor_readings: Mapped[list[SensorReading]] = relationship(back_populates="pump")
    alarms: Mapped[list[Alarm]] = relationship(back_populates="pump")
    nozzles: Mapped[list[Nozzle]] = relationship(back_populates="pump")

    # Fuel type is deliberately not duplicated here; use pump.tank.fuel_type.
