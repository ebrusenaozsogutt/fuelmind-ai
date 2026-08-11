"""Add durable simulation runs, events, and tick provenance.

Revision ID: 20260807_0002
Revises: 20260804_0001
Create Date: 2026-08-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260807_0002"
down_revision: str | None = "20260804_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create simulation lifecycle tables and link generated records to their run."""

    bind = op.get_bind()
    source_type = postgresql.ENUM(
        "SIMULATION", "CSV_IMPORT", "REAL_DEVICE", "MANUAL", name="source_type"
    )
    source_type.create(bind, checkfirst=True)

    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="simulation_status", create_type=False),
            nullable=False,
        ),
        sa.Column("current_simulation_time", sa.DateTime(timezone=True)),
        sa.Column("sequence_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_sensor_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_sale_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_delivery_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("real_started_at", sa.DateTime(timezone=True)),
        sa.Column("real_ended_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(length=2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_simulation_runs_station_id", "simulation_runs", ["station_id"])
    op.create_index("ix_simulation_runs_status", "simulation_runs", ["status"])

    op.create_table(
        "simulation_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "simulation_run_id",
            sa.Integer(),
            sa.ForeignKey("simulation_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_type", sa.String(length=50)),
        sa.Column("target_id", sa.String(length=100)),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_simulation_events_simulation_run_id", "simulation_events", ["simulation_run_id"]
    )
    op.create_index("ix_simulation_events_station_id", "simulation_events", ["station_id"])

    with op.batch_alter_table("sensor_readings") as batch:
        batch.add_column(sa.Column("simulation_run_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sequence_number", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("true_tank_level", sa.Numeric(14, 3), nullable=True))
        batch.add_column(sa.Column("pump_temperature", sa.Numeric(6, 2), nullable=True))
        batch.add_column(
            sa.Column(
                "source_type",
                source_type,
                nullable=False,
                server_default="MANUAL",
            )
        )
        batch.create_foreign_key(
            "fk_sensor_readings_simulation_run_id",
            "simulation_runs",
            ["simulation_run_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_sensor_readings_simulation_run_id", ["simulation_run_id"]
        )

    with op.batch_alter_table("sales") as batch:
        batch.add_column(sa.Column("simulation_run_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("simulation_sale_id", sa.String(length=100), nullable=True))
        batch.create_foreign_key(
            "fk_sales_simulation_run_id",
            "simulation_runs",
            ["simulation_run_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_sales_simulation_run_id", ["simulation_run_id"])
        batch.create_unique_constraint("uq_sales_simulation_sale_id", ["simulation_sale_id"])

    with op.batch_alter_table("deliveries") as batch:
        batch.add_column(sa.Column("simulation_run_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("simulation_delivery_id", sa.String(length=150), nullable=True)
        )
        batch.create_foreign_key(
            "fk_deliveries_simulation_run_id",
            "simulation_runs",
            ["simulation_run_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_deliveries_simulation_run_id", ["simulation_run_id"])
        batch.create_unique_constraint(
            "uq_deliveries_simulation_delivery_id", ["simulation_delivery_id"]
        )


def downgrade() -> None:
    """Remove tick-persistence structures in dependency order."""

    with op.batch_alter_table("deliveries") as batch:
        batch.drop_constraint("uq_deliveries_simulation_delivery_id", type_="unique")
        batch.drop_index("ix_deliveries_simulation_run_id")
        batch.drop_constraint("fk_deliveries_simulation_run_id", type_="foreignkey")
        batch.drop_column("simulation_delivery_id")
        batch.drop_column("simulation_run_id")
    with op.batch_alter_table("sales") as batch:
        batch.drop_constraint("uq_sales_simulation_sale_id", type_="unique")
        batch.drop_index("ix_sales_simulation_run_id")
        batch.drop_constraint("fk_sales_simulation_run_id", type_="foreignkey")
        batch.drop_column("simulation_sale_id")
        batch.drop_column("simulation_run_id")
    with op.batch_alter_table("sensor_readings") as batch:
        batch.drop_index("ix_sensor_readings_simulation_run_id")
        batch.drop_constraint("fk_sensor_readings_simulation_run_id", type_="foreignkey")
        batch.drop_column("source_type")
        batch.drop_column("pump_temperature")
        batch.drop_column("true_tank_level")
        batch.drop_column("sequence_number")
        batch.drop_column("simulation_run_id")

    op.drop_index("ix_simulation_events_station_id", table_name="simulation_events")
    op.drop_index("ix_simulation_events_simulation_run_id", table_name="simulation_events")
    op.drop_table("simulation_events")
    op.drop_index("ix_simulation_runs_status", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_station_id", table_name="simulation_runs")
    op.drop_table("simulation_runs")
    postgresql.ENUM(name="source_type").drop(op.get_bind(), checkfirst=True)
