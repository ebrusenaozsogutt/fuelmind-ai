"""Tank probe database model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import ProbeStatus

if TYPE_CHECKING:
    from app.models.communication_port import CommunicationPort
    from app.models.probe_reading import ProbeReading
    from app.models.tank import Tank


class TankProbe(Base):
    """A physical level-measurement device installed in a tank."""

    __tablename__ = "tank_probes"
    __table_args__ = (
        Index("ix_tank_probes_tank_id", "tank_id"),
        Index(
            "uq_tank_probes_active_tank",
            "tank_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tank_id: Mapped[int] = mapped_column(
        ForeignKey("tanks.id", ondelete="RESTRICT"), nullable=False
    )
    communication_port_id: Mapped[int | None] = mapped_column(
        ForeignKey("communication_ports.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    device_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ProbeStatus] = mapped_column(
        SqlEnum(
            ProbeStatus,
            name="probe_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=ProbeStatus.UNKNOWN,
        nullable=False,
    )
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_communication_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    tank: Mapped[Tank] = relationship(back_populates="tank_probes")
    communication_port: Mapped[CommunicationPort | None] = relationship(
        back_populates="tank_probes"
    )
    readings: Mapped[list[ProbeReading]] = relationship(back_populates="probe")
