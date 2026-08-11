"""Add a nullable target timestamp for dataset-run progress.

Revision ID: 20260807_0006
Revises: 20260807_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0006"
down_revision: str | None = "20260807_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("simulation_runs", sa.Column("target_simulation_time", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_runs", "target_simulation_time")
