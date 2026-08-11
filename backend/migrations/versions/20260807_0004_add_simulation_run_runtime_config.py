"""Add persisted simulation runtime configuration.

Revision ID: 20260807_0004
Revises: 20260807_0003
Create Date: 2026-08-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.utils.simulation_defaults import (
    DEFAULT_PERSIST_EVERY_N_TICKS,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_STEP_SECONDS,
    DEFAULT_SPEED_MULTIPLIER,
    DEFAULT_TICK_INTERVAL_MS,
)


revision: str = "20260807_0004"
down_revision: str | None = "20260807_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill non-null runtime configuration for existing simulation runs."""

    bind = op.get_bind()
    simulation_mode = postgresql.ENUM(
        "REALTIME", "ACCELERATED", "DATASET", name="simulation_mode"
    )
    simulation_mode.create(bind, checkfirst=True)
    with op.batch_alter_table("simulation_runs") as batch:
        batch.add_column(
            sa.Column(
                "mode",
                simulation_mode,
                nullable=False,
                server_default="REALTIME",
            )
        )
        batch.add_column(
            sa.Column(
                "tick_interval_ms",
                sa.Integer(),
                nullable=False,
                server_default=str(DEFAULT_TICK_INTERVAL_MS),
            )
        )
        batch.add_column(
            sa.Column(
                "simulation_step_seconds",
                sa.Integer(),
                nullable=False,
                server_default=str(DEFAULT_SIMULATION_STEP_SECONDS),
            )
        )
        batch.add_column(
            sa.Column(
                "speed_multiplier",
                sa.Numeric(12, 4),
                nullable=False,
                server_default=str(DEFAULT_SPEED_MULTIPLIER),
            )
        )
        batch.add_column(
            sa.Column(
                "random_seed",
                sa.Integer(),
                nullable=False,
                server_default=str(DEFAULT_RANDOM_SEED),
            )
        )
        batch.add_column(
            sa.Column(
                "persist_every_n_ticks",
                sa.Integer(),
                nullable=False,
                server_default=str(DEFAULT_PERSIST_EVERY_N_TICKS),
            )
        )
        batch.create_check_constraint(
            "ck_simulation_runs_tick_interval", "tick_interval_ms > 0"
        )
        batch.create_check_constraint(
            "ck_simulation_runs_step_seconds", "simulation_step_seconds > 0"
        )
        batch.create_check_constraint(
            "ck_simulation_runs_speed_multiplier", "speed_multiplier > 0"
        )
        batch.create_check_constraint(
            "ck_simulation_runs_persist_frequency", "persist_every_n_ticks > 0"
        )


def downgrade() -> None:
    """Remove configuration columns while leaving PostgreSQL enum type safe to reuse."""

    with op.batch_alter_table("simulation_runs") as batch:
        batch.drop_constraint("ck_simulation_runs_persist_frequency", type_="check")
        batch.drop_constraint("ck_simulation_runs_speed_multiplier", type_="check")
        batch.drop_constraint("ck_simulation_runs_step_seconds", type_="check")
        batch.drop_constraint("ck_simulation_runs_tick_interval", type_="check")
        batch.drop_column("persist_every_n_ticks")
        batch.drop_column("random_seed")
        batch.drop_column("speed_multiplier")
        batch.drop_column("simulation_step_seconds")
        batch.drop_column("tick_interval_ms")
        batch.drop_column("mode")
    postgresql.ENUM(name="simulation_mode").drop(op.get_bind(), checkfirst=True)
