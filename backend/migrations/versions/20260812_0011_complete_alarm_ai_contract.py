"""Complete the persisted AI detail contract for alarms.

Revision ID: 20260812_0011
Revises: 20260812_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0011"
down_revision: str | None = "20260812_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("alarms", sa.Column("risk_level", sa.String(length=20), nullable=True))
    op.add_column("alarms", sa.Column("anomaly_type", sa.String(length=50), nullable=True))
    op.add_column("alarms", sa.Column("model_outlier", sa.Boolean(), nullable=True))
    op.add_column(
        "alarms",
        sa.Column("triggered_rules_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alarms", "triggered_rules_json")
    op.drop_column("alarms", "model_outlier")
    op.drop_column("alarms", "anomaly_type")
    op.drop_column("alarms", "risk_level")
