"""Allow overnight card windows and enforce completed-sale totalizer arithmetic."""

from alembic import op


revision = "20260826_0019"
down_revision = "20260818_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_fuel_card_usage_windows_time_range",
        "fuel_card_usage_windows",
        type_="check",
    )
    op.create_check_constraint(
        "ck_sales_totalizer_quantity_matches",
        "sales",
        "start_totalizer_liters IS NULL OR end_totalizer_liters IS NULL "
        "OR ABS((end_totalizer_liters - start_totalizer_liters) - quantity_liters) <= 0.001",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sales_totalizer_quantity_matches", "sales", type_="check")
    op.create_check_constraint(
        "ck_fuel_card_usage_windows_time_range",
        "fuel_card_usage_windows",
        "end_time > start_time",
    )
