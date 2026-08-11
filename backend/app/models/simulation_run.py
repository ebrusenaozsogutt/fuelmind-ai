"""Persisted lifecycle state for a station simulation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.datetime_utils import utc_now
from app.utils.enums import SimulationMode, SimulationStatus
from app.utils.simulation_defaults import (
    DEFAULT_PERSIST_EVERY_N_TICKS,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_STEP_SECONDS,
    DEFAULT_SPEED_MULTIPLIER,
    DEFAULT_TICK_INTERVAL_MS,
)

if TYPE_CHECKING:
    from app.models.simulation_event import SimulationEvent
    from app.models.station import Station
    from app.models.simulation_scenario import SimulationScenario


class SimulationRun(Base):
    """One executable simulation run for a station."""

    __tablename__ = "simulation_runs"
    __table_args__ = (
        CheckConstraint("tick_interval_ms > 0", name="ck_simulation_runs_tick_interval"),
        CheckConstraint(
            "simulation_step_seconds > 0",
            name="ck_simulation_runs_step_seconds",
        ),
        CheckConstraint(
            "speed_multiplier > 0", name="ck_simulation_runs_speed_multiplier"
        ),
        CheckConstraint(
            "persist_every_n_ticks > 0",
            name="ck_simulation_runs_persist_frequency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
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
        index=True,
    )
    simulation_start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    mode: Mapped[SimulationMode] = mapped_column(
        SqlEnum(
            SimulationMode,
            name="simulation_mode",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        default=SimulationMode.REALTIME,
        nullable=False,
    )
    tick_interval_ms: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_TICK_INTERVAL_MS, nullable=False
    )
    simulation_step_seconds: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_SIMULATION_STEP_SECONDS, nullable=False
    )
    speed_multiplier: Mapped[float] = mapped_column(
        Numeric(12, 4), default=DEFAULT_SPEED_MULTIPLIER, nullable=False
    )
    random_seed: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_RANDOM_SEED, nullable=False
    )
    persist_every_n_ticks: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_PERSIST_EVERY_N_TICKS, nullable=False
    )
    current_simulation_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    target_simulation_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_sensor_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_sale_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_delivery_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    real_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    real_ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    station: Mapped[Station] = relationship(back_populates="simulation_runs")
    events: Mapped[list[SimulationEvent]] = relationship(back_populates="simulation_run")
    scenarios: Mapped[list[SimulationScenario]] = relationship(
        cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs: object) -> None:
        """Apply runtime defaults consistently before a run reaches the database."""

        defaults = {
            "mode": SimulationMode.REALTIME,
            "tick_interval_ms": DEFAULT_TICK_INTERVAL_MS,
            "simulation_step_seconds": DEFAULT_SIMULATION_STEP_SECONDS,
            "speed_multiplier": DEFAULT_SPEED_MULTIPLIER,
            "random_seed": DEFAULT_RANDOM_SEED,
            "persist_every_n_ticks": DEFAULT_PERSIST_EVERY_N_TICKS,
        }
        for field, value in defaults.items():
            kwargs.setdefault(field, value)
        super().__init__(**kwargs)

    @property
    def progress_percent(self) -> float | None:
        """Return the persisted dataset-run progress without storing a DB column."""

        if self.mode != SimulationMode.DATASET or self.target_simulation_time is None:
            return None

        total_seconds = (
            self.target_simulation_time - self.simulation_start_time
        ).total_seconds()
        current_time = self.current_simulation_time or self.simulation_start_time
        if self.status == SimulationStatus.COMPLETED:
            return 100.0
        if total_seconds <= 0:
            return 0.0
        progress = 100 * (
            current_time - self.simulation_start_time
        ).total_seconds() / total_seconds
        return max(0.0, min(100.0, progress))
