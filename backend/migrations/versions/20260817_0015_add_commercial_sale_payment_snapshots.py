"""Add credit usage and payment-type snapshots for commercial sales.

Revision ID: 20260817_0015
Revises: 20260817_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260817_0015"
down_revision: str | None = "20260817_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Additive financial state required for safe credit-card settlement."""

    op.add_column(
        "fuel_cards",
        sa.Column(
            "credit_used",
            sa.Numeric(16, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.alter_column("fuel_cards", "credit_used", server_default=None)
    op.create_check_constraint(
        "ck_fuel_cards_credit_used_nonnegative", "fuel_cards", "credit_used >= 0"
    )
    op.add_column(
        "sales",
        sa.Column(
            "payment_type",
            postgresql.ENUM(name="payment_type", create_type=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove the additive Prompt 7 settlement columns."""

    op.drop_column("sales", "payment_type")
    op.drop_constraint(
        "ck_fuel_cards_credit_used_nonnegative", "fuel_cards", type_="check"
    )
    op.drop_column("fuel_cards", "credit_used")
