"""Forecourt device controller database model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import ControllerStatus, ControllerType

if TYPE_CHECKING:
    from app.models.communication_port import CommunicationPort
    from app.models.station import Station


class DeviceController(Base):
    """A station-owned controller for forecourt communication devices."""

    __tablename__ = "device_controllers"
    __table_args__ = (
        UniqueConstraint("station_id", "code", name="uq_device_controllers_station_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    controller_type: Mapped[ControllerType] = mapped_column(
        SqlEnum(
            ControllerType,
            name="controller_type",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=ControllerType.GENERIC,
        nullable=False,
    )
    status: Mapped[ControllerStatus] = mapped_column(
        SqlEnum(
            ControllerStatus,
            name="controller_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=ControllerStatus.OFFLINE,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    station: Mapped[Station] = relationship(back_populates="device_controllers")
    communication_ports: Mapped[list[CommunicationPort]] = relationship(
        back_populates="controller", cascade="save-update, merge"
    )
