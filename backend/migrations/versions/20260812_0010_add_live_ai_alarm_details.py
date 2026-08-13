"""Add live AI context to existing alarms.

Revision ID: 20260812_0010
Revises: 20260812_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0010"
down_revision: str | None = "20260812_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("alarms", sa.Column("decision_source", sa.String(length=30), nullable=True))
    op.add_column("alarms", sa.Column("model_version", sa.String(length=50), nullable=True))
    op.add_column("alarms", sa.Column("findings_json", postgresql.JSONB(), nullable=True))
    op.add_column("alarms", sa.Column("recommended_checks_json", postgresql.JSONB(), nullable=True))
    op.add_column("alarms", sa.Column("data_quality_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("alarms", "data_quality_note")
    op.drop_column("alarms", "recommended_checks_json")
    op.drop_column("alarms", "findings_json")
    op.drop_column("alarms", "model_version")
    op.drop_column("alarms", "decision_source")
