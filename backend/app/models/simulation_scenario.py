"""Simulation scenario database model."""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import SimulationStatus, SimulationTargetType


class SimulationScenario(Base):
    """A configurable simulation for a station, tank, or pump target."""

    __tablename__ = "simulation_scenarios"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes > 0", name="ck_simulation_scenarios_duration_positive"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    target_type: Mapped[SimulationTargetType] = mapped_column(
        SqlEnum(
            SimulationTargetType,
            name="simulation_target_type",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    target_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[SimulationStatus] = mapped_column(
        SqlEnum(
            SimulationStatus,
            name="simulation_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=SimulationStatus.CREATED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
