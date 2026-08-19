"""Device controller communication port database model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import PortStatus, PortType

if TYPE_CHECKING:
    from app.models.device_controller import DeviceController
    from app.models.pump import Pump
    from app.models.tank_probe import TankProbe


class CommunicationPort(Base):
    """A logical communication port exposed by a device controller."""

    __tablename__ = "communication_ports"
    __table_args__ = (
        UniqueConstraint(
            "controller_id", "port_number", name="uq_communication_ports_controller_number"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    controller_id: Mapped[int] = mapped_column(
        ForeignKey("device_controllers.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    port_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    port_type: Mapped[PortType] = mapped_column(
        SqlEnum(
            PortType,
            name="port_type",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=PortType.GENERIC,
        nullable=False,
    )
    protocol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    baud_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[PortStatus] = mapped_column(
        SqlEnum(
            PortStatus,
            name="port_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=PortStatus.OFFLINE,
        nullable=False,
    )
    device_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_communication_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    controller: Mapped[DeviceController] = relationship(back_populates="communication_ports")
    pumps: Mapped[list[Pump]] = relationship(back_populates="communication_port")
    tank_probes: Mapped[list[TankProbe]] = relationship(
        back_populates="communication_port"
    )

    @property
    def controller_code(self) -> str:
        """Expose a compact controller label for management API responses."""

        return self.controller.code

    @property
    def station_id(self) -> int:
        """Expose the controller's station without duplicating it in the table."""

        return self.controller.station_id
