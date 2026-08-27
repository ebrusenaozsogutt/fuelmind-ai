"""Support field-device scenario targets and preserve alarm target context."""

from alembic import op
import sqlalchemy as sa


revision = "20260826_0020"
down_revision = "20260826_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alarms", sa.Column("target_type", sa.String(length=30), nullable=True))
    op.add_column("alarms", sa.Column("target_id", sa.Integer(), nullable=True))
    op.create_index("ix_alarms_target_type", "alarms", ["target_type"])
    op.create_index("ix_alarms_target_id", "alarms", ["target_id"])
    for value in ("CONTROLLER", "PORT", "PROBE"):
        op.execute(f"ALTER TYPE simulation_target_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    op.drop_index("ix_alarms_target_id", table_name="alarms")
    op.drop_index("ix_alarms_target_type", table_name="alarms")
    op.drop_column("alarms", "target_id")
    op.drop_column("alarms", "target_type")
