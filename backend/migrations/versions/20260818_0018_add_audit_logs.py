"""Add immutable critical-change audit logs.

Revision ID: 20260818_0018
Revises: 20260818_0017
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_0018"
down_revision = "20260818_0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("username_snapshot", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("old_values_json", postgresql.JSONB(), nullable=True),
        sa.Column("new_values_json", postgresql.JSONB(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_station_id", "audit_logs", ["station_id"])


def downgrade():
    for name in ("ix_audit_logs_station_id", "ix_audit_logs_entity", "ix_audit_logs_user_id", "ix_audit_logs_created_at"):
        op.drop_index(name, table_name="audit_logs")
    op.drop_table("audit_logs")
