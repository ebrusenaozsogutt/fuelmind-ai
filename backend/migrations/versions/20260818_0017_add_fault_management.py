"""Add durable fault management records.

Revision ID: 20260818_0017
Revises: 20260818_0016
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_0017"
down_revision = "20260818_0016"
branch_labels = None
depends_on = None


ENUMS = (
    ("fault_status", ("OPEN", "INVESTIGATING", "RESOLVED")),
    (
        "fault_type",
        ("COMMUNICATION", "CONNECTION", "INITIALIZATION", "INTERFACE", "SENSOR", "EQUIPMENT", "NOZZLE"),
    ),
    (
        "fault_code",
        (
            "INTERFACE_ERROR",
            "PUMP_NOT_CONNECTED",
            "USC_INITIALIZATION_ERROR",
            "PORT_COMMUNICATION_ERROR",
            "PROBE_COMMUNICATION_ERROR",
            "SENSOR_ERROR",
            "NOZZLE_ERROR",
        ),
    ),
    ("fault_target_type", ("CONTROLLER", "PORT", "PUMP", "PROBE", "NOZZLE", "TANK", "SENSOR")),
)


def enum_column(name):
    return postgresql.ENUM(name=name, create_type=False)


def upgrade():
    bind = op.get_bind()
    for name, values in ENUMS:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.create_table(
        "faults",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("alarm_id", sa.Integer(), sa.ForeignKey("alarms.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("target_type", enum_column("fault_target_type"), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("fault_type", enum_column("fault_type"), nullable=False),
        sa.Column("fault_code", enum_column("fault_code"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("status", enum_column("fault_status"), nullable=False, server_default=sa.text("'OPEN'::fault_status")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("alarm_id", name="uq_faults_alarm_id"),
    )
    op.alter_column("faults", "status", server_default=None)
    op.create_index("ix_faults_station_id", "faults", ["station_id"])
    op.create_index("ix_faults_target_id", "faults", ["target_id"])
    op.create_index("ix_faults_resolved_by", "faults", ["resolved_by"])
    op.create_index("ix_faults_station_detected_at", "faults", ["station_id", "detected_at"])
    op.create_index("ix_faults_fault_code", "faults", ["fault_code"])
    op.create_index("ix_faults_status", "faults", ["status"])
    op.create_index("ix_faults_alarm_id", "faults", ["alarm_id"])


def downgrade():
    for name in ("ix_faults_alarm_id", "ix_faults_status", "ix_faults_fault_code", "ix_faults_station_detected_at", "ix_faults_resolved_by", "ix_faults_target_id", "ix_faults_station_id"):
        op.drop_index(name, table_name="faults")
    op.drop_table("faults")
    bind = op.get_bind()
    for name, values in reversed(ENUMS):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
