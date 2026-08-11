"""Add transient lifecycle statuses required by the simulation runner.

Revision ID: 20260807_0003
Revises: 20260807_0002
Create Date: 2026-08-07 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260807_0003"
down_revision: str | None = "20260807_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the runner's explicit start and stop transition states."""

    op.execute("ALTER TYPE simulation_status ADD VALUE IF NOT EXISTS 'STARTING'")
    op.execute("ALTER TYPE simulation_status ADD VALUE IF NOT EXISTS 'STOPPING'")


def downgrade() -> None:
    """Keep PostgreSQL enum values because removing them requires type recreation."""

    # PostgreSQL does not support DROP VALUE for enums. Retaining unused values is
    # safer than recreating a production enum that is referenced by existing rows.
