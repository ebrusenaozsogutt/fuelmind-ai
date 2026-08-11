"""Add simulation run ownership and requested start time.

Revision ID: 20260807_0005
Revises: 20260807_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0005"
down_revision: str | None = "20260807_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill a start time while preserving existing runs and their ownership gap."""

    with op.batch_alter_table("simulation_runs") as batch:
        batch.add_column(
            sa.Column(
                "simulation_start_time",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch.add_column(sa.Column("created_by", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_simulation_runs_created_by",
            "users",
            ["created_by"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    """Remove API ownership and requested-start metadata."""

    with op.batch_alter_table("simulation_runs") as batch:
        batch.drop_constraint("fk_simulation_runs_created_by", type_="foreignkey")
        batch.drop_column("created_by")
        batch.drop_column("simulation_start_time")
