"""Add persistent per-transaction fuel-card limits.

Revision ID: 20260817_0014
Revises: 20260817_0013
"""
from collections.abc import Sequence
from alembic import op

revision: str = "20260817_0014"
down_revision: str | None = "20260817_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    """Append the value without rewriting existing limit records."""
    op.execute("ALTER TYPE card_limit_type ADD VALUE IF NOT EXISTS 'PER_TRANSACTION'")

def downgrade() -> None:
    """PostgreSQL cannot safely remove enum values without a type rewrite.

    The additive value is intentionally retained to preserve stored data.
    """
    pass
