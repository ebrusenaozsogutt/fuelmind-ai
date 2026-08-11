"""Link each persisted scenario to the simulation run that owns it.

Revision ID: 20260810_0007
Revises: 20260807_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0007"
down_revision: str | None = "20260807_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("simulation_scenarios", sa.Column("simulation_run_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_simulation_scenarios_run", "simulation_scenarios", "simulation_runs", ["simulation_run_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_simulation_scenarios_simulation_run_id", "simulation_scenarios", ["simulation_run_id"])


def downgrade() -> None:
    op.drop_index("ix_simulation_scenarios_simulation_run_id", table_name="simulation_scenarios")
    op.drop_constraint("fk_simulation_scenarios_run", "simulation_scenarios", type_="foreignkey")
    op.drop_column("simulation_scenarios", "simulation_run_id")
