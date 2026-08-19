"""Add forecourt controller, communication-port, probe, and nozzle topology.

Revision ID: 20260814_0012
Revises: 20260812_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260814_0012"
down_revision: str | None = "20260812_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the additive field-device topology without changing existing data."""

    bind = op.get_bind()
    controller_type = postgresql.ENUM("USC", "GENERIC", name="controller_type")
    controller_status = postgresql.ENUM(
        "ONLINE", "OFFLINE", "ERROR", "STARTING", name="controller_status"
    )
    port_type = postgresql.ENUM("PUMP", "PROBE", "GENERIC", name="port_type")
    port_status = postgresql.ENUM(
        "ONLINE", "OFFLINE", "DEGRADED", "ERROR", name="port_status"
    )
    probe_status = postgresql.ENUM(
        "ONLINE", "OFFLINE", "FAULT", "UNKNOWN", name="probe_status"
    )
    nozzle_status = postgresql.ENUM(
        "AVAILABLE", "DISPENSING", "OUT_OF_SERVICE", "FAULT", name="nozzle_status"
    )
    for enum_type in (
        controller_type,
        controller_status,
        port_type,
        port_status,
        probe_status,
        nozzle_status,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "device_controllers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column(
            "controller_type",
            postgresql.ENUM(name="controller_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="controller_status", create_type=False),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_communication_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("station_id", "code", name="uq_device_controllers_station_code"),
    )
    op.create_index(
        "ix_device_controllers_station_id", "device_controllers", ["station_id"]
    )

    op.create_table(
        "communication_ports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "controller_id",
            sa.Integer(),
            sa.ForeignKey("device_controllers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("port_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column(
            "port_type",
            postgresql.ENUM(name="port_type", create_type=False),
            nullable=False,
        ),
        sa.Column("protocol", sa.String(length=100), nullable=True),
        sa.Column("baud_rate", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="port_status", create_type=False),
            nullable=False,
        ),
        sa.Column("device_path", sa.String(length=255), nullable=True),
        sa.Column("last_communication_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "controller_id", "port_number", name="uq_communication_ports_controller_number"
        ),
    )
    op.create_index(
        "ix_communication_ports_controller_id", "communication_ports", ["controller_id"]
    )

    op.create_table(
        "tank_probes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tank_id",
            sa.Integer(),
            sa.ForeignKey("tanks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "communication_port_id",
            sa.Integer(),
            sa.ForeignKey("communication_ports.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("device_address", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="probe_status", create_type=False),
            nullable=False,
        ),
        sa.Column("manufacturer", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_communication_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tank_probes_tank_id", "tank_probes", ["tank_id"])
    op.create_index(
        "ix_tank_probes_communication_port_id",
        "tank_probes",
        ["communication_port_id"],
    )
    op.create_index(
        "uq_tank_probes_active_tank",
        "tank_probes",
        ["tank_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "probe_readings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "probe_id",
            sa.Integer(),
            sa.ForeignKey("tank_probes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tank_id",
            sa.Integer(),
            sa.ForeignKey("tanks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "simulation_run_id",
            sa.Integer(),
            sa.ForeignKey("simulation_runs.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("reading_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fuel_height_mm", sa.Numeric(14, 3), nullable=True),
        sa.Column("fuel_volume_liters", sa.Numeric(14, 3), nullable=True),
        sa.Column("water_height_mm", sa.Numeric(14, 3), nullable=True),
        sa.Column("water_volume_liters", sa.Numeric(14, 3), nullable=True),
        sa.Column("temperature_celsius", sa.Numeric(6, 2), nullable=True),
        sa.Column("data_quality_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("quality_flags_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM(name="source_type", create_type=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "fuel_height_mm IS NULL OR fuel_height_mm >= 0",
            name="ck_probe_readings_fuel_height_nonnegative",
        ),
        sa.CheckConstraint(
            "fuel_volume_liters IS NULL OR fuel_volume_liters >= 0",
            name="ck_probe_readings_fuel_volume_nonnegative",
        ),
        sa.CheckConstraint(
            "water_height_mm IS NULL OR water_height_mm >= 0",
            name="ck_probe_readings_water_height_nonnegative",
        ),
        sa.CheckConstraint(
            "water_volume_liters IS NULL OR water_volume_liters >= 0",
            name="ck_probe_readings_water_volume_nonnegative",
        ),
        sa.CheckConstraint(
            "data_quality_score BETWEEN 0 AND 100",
            name="ck_probe_readings_quality_score_range",
        ),
    )
    op.create_index(
        "ix_probe_readings_probe_id", "probe_readings", ["probe_id"]
    )
    op.create_index("ix_probe_readings_tank_id", "probe_readings", ["tank_id"])
    op.create_index(
        "ix_probe_readings_simulation_run_id", "probe_readings", ["simulation_run_id"]
    )
    op.create_index(
        "ix_probe_readings_probe_timestamp",
        "probe_readings",
        ["probe_id", "reading_timestamp"],
    )
    op.create_index(
        "ix_probe_readings_tank_timestamp",
        "probe_readings",
        ["tank_id", "reading_timestamp"],
    )

    op.add_column(
        "pumps", sa.Column("communication_port_id", sa.Integer(), nullable=True)
    )
    op.add_column("pumps", sa.Column("device_address", sa.String(length=100), nullable=True))
    op.create_foreign_key(
        "fk_pumps_communication_port_id",
        "pumps",
        "communication_ports",
        ["communication_port_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_pumps_communication_port_id", "pumps", ["communication_port_id"])

    op.create_table(
        "nozzles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "pump_id",
            sa.Integer(),
            sa.ForeignKey("pumps.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "fuel_type_id",
            sa.Integer(),
            sa.ForeignKey("fuel_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("nozzle_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="nozzle_status", create_type=False),
            nullable=False,
        ),
        sa.Column("totalizer_liters", sa.Numeric(14, 3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("pump_id", "nozzle_number", name="uq_nozzles_pump_number"),
        sa.CheckConstraint(
            "totalizer_liters >= 0", name="ck_nozzles_totalizer_nonnegative"
        ),
    )
    op.create_index("ix_nozzles_pump_id", "nozzles", ["pump_id"])
    op.create_index("ix_nozzles_fuel_type_id", "nozzles", ["fuel_type_id"])


def downgrade() -> None:
    """Remove Stage 9 topology structures in dependency order."""

    op.drop_index("ix_nozzles_fuel_type_id", table_name="nozzles")
    op.drop_index("ix_nozzles_pump_id", table_name="nozzles")
    op.drop_table("nozzles")

    op.drop_index("ix_pumps_communication_port_id", table_name="pumps")
    op.drop_constraint(
        "fk_pumps_communication_port_id", "pumps", type_="foreignkey"
    )
    op.drop_column("pumps", "device_address")
    op.drop_column("pumps", "communication_port_id")

    op.drop_index("ix_probe_readings_tank_timestamp", table_name="probe_readings")
    op.drop_index("ix_probe_readings_probe_timestamp", table_name="probe_readings")
    op.drop_index("ix_probe_readings_simulation_run_id", table_name="probe_readings")
    op.drop_index("ix_probe_readings_tank_id", table_name="probe_readings")
    op.drop_index("ix_probe_readings_probe_id", table_name="probe_readings")
    op.drop_table("probe_readings")

    op.drop_index("uq_tank_probes_active_tank", table_name="tank_probes")
    op.drop_index("ix_tank_probes_communication_port_id", table_name="tank_probes")
    op.drop_index("ix_tank_probes_tank_id", table_name="tank_probes")
    op.drop_table("tank_probes")

    op.drop_index("ix_communication_ports_controller_id", table_name="communication_ports")
    op.drop_table("communication_ports")
    op.drop_index("ix_device_controllers_station_id", table_name="device_controllers")
    op.drop_table("device_controllers")

    bind = op.get_bind()
    for name in (
        "nozzle_status",
        "probe_status",
        "port_status",
        "port_type",
        "controller_status",
        "controller_type",
    ):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
