"""Add durable data-quality flags to sensor readings.

Revision ID: 20260810_0008
Revises: 20260810_0007
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0008"
down_revision: str | None = "20260810_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("sensor_readings", sa.Column("quality_flags_json", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.alter_column("sensor_readings", "quality_flags_json", server_default=None)

def downgrade() -> None:
    op.drop_column("sensor_readings", "quality_flags_json")
