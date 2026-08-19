"""Add the Stage 10 commercial customer, card, price, and sale foundation.

Revision ID: 20260817_0013
Revises: 20260814_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260817_0013"
down_revision: str | None = "20260814_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUM_DEFINITIONS = (
    ("customer_type", ("COMPANY", "INDIVIDUAL")),
    ("customer_request_status", ("PENDING", "APPROVED", "REJECTED", "SUSPENDED")),
    ("card_status", ("ACTIVE", "PASSIVE", "BLOCKED", "EXPIRED")),
    ("card_limit_type", ("DAILY", "WEEKLY", "MONTHLY", "CUSTOM")),
    ("payment_type", ("PREPAID", "CREDIT")),
    ("sale_status", ("AUTHORIZED", "STARTED", "COMPLETED", "CANCELLED", "FAILED")),
    ("driver_assignment_status", ("ACTIVE", "COMPLETED", "CANCELLED")),
)


def enum_column(name: str) -> postgresql.ENUM:
    """Reference an enum type which has already been created in this revision."""

    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    """Create additive commercial tables and extend legacy sales safely."""

    bind = op.get_bind()
    for name, values in ENUM_DEFINITIONS:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    customer_type = enum_column("customer_type")
    request_status = enum_column("customer_request_status")
    card_status = enum_column("card_status")
    card_limit_type = enum_column("card_limit_type")
    payment_type = enum_column("payment_type")
    sale_status = enum_column("sale_status")
    assignment_status = enum_column("driver_assignment_status")

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("customer_type", customer_type, nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("tax_number", sa.String(length=32), nullable=True),
        sa.Column("tax_office", sa.String(length=150), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("registration_date", sa.Date(), nullable=False),
        sa.Column("discount_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("request_status", request_status, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_customers_code"),
        sa.CheckConstraint("discount_rate >= 0", name="ck_customers_discount_nonnegative"),
        sa.CheckConstraint("discount_rate <= 100", name="ck_customers_discount_maximum"),
    )
    op.create_index("ix_customers_code", "customers", ["code"], unique=True)
    op.create_index("ix_customers_name", "customers", ["name"])

    op.create_table(
        "customer_authorized_persons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customer_authorized_persons_customer_id", "customer_authorized_persons", ["customer_id"])

    op.create_table(
        "fleets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("request_status", request_status, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("customer_id", "code", name="uq_fleets_customer_code"),
    )
    op.create_index("ix_fleets_customer_id", "fleets", ["customer_id"])

    op.create_table(
        "fleet_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fleet_id", sa.Integer(), sa.ForeignKey("fleets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fleet_id", "code", name="uq_fleet_groups_fleet_code"),
    )
    op.create_index("ix_fleet_groups_fleet_id", "fleet_groups", ["fleet_id"])

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fleet_group_id", sa.Integer(), sa.ForeignKey("fleet_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plate", sa.String(length=32), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("vehicle_type", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plate", name="uq_vehicles_plate"),
    )
    op.create_index("ix_vehicles_fleet_group_id", "vehicles", ["fleet_group_id"])
    op.create_index("ix_vehicles_plate", "vehicles", ["plate"], unique=True)

    op.create_table(
        "drivers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("reference_code", sa.String(length=32), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("license_number", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("reference_code", name="uq_drivers_reference_code"),
    )
    op.create_index("ix_drivers_reference_code", "drivers", ["reference_code"], unique=True)

    op.create_table(
        "driver_vehicle_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("driver_id", sa.Integer(), sa.ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_from", sa.Date(), nullable=False),
        sa.Column("assigned_until", sa.Date(), nullable=True),
        sa.Column("status", assignment_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("assigned_until IS NULL OR assigned_until >= assigned_from", name="ck_driver_vehicle_assignments_date_range"),
    )
    op.create_index("ix_driver_vehicle_assignments_driver_id", "driver_vehicle_assignments", ["driver_id"])
    op.create_index("ix_driver_vehicle_assignments_vehicle_id", "driver_vehicle_assignments", ["vehicle_id"])

    op.create_table(
        "fuel_cards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("card_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("unit_id", sa.String(length=100), nullable=False),
        sa.Column("status", card_status, nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("payment_type", payment_type, nullable=False),
        sa.Column("prepaid_balance", sa.Numeric(16, 2), nullable=False),
        sa.Column("credit_limit", sa.Numeric(16, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("card_code", name="uq_fuel_cards_card_code"),
        sa.UniqueConstraint("unit_id", name="uq_fuel_cards_unit_id"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until >= valid_from", name="ck_fuel_cards_validity_range"),
        sa.CheckConstraint("prepaid_balance >= 0", name="ck_fuel_cards_prepaid_nonnegative"),
        sa.CheckConstraint("credit_limit >= 0", name="ck_fuel_cards_credit_nonnegative"),
    )
    op.create_index("ix_fuel_cards_vehicle_id", "fuel_cards", ["vehicle_id"])
    op.create_index("ix_fuel_cards_card_code", "fuel_cards", ["card_code"], unique=True)
    op.create_index("ix_fuel_cards_unit_id", "fuel_cards", ["unit_id"], unique=True)

    op.create_table(
        "fuel_card_limits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fuel_card_id", sa.Integer(), sa.ForeignKey("fuel_cards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("limit_type", card_limit_type, nullable=False),
        sa.Column("quantity_limit_liters", sa.Numeric(14, 3), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_limit_liters > 0", name="ck_fuel_card_limits_quantity_positive"),
        sa.CheckConstraint("valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="ck_fuel_card_limits_validity_range"),
    )
    op.create_index("ix_fuel_card_limits_fuel_card_id", "fuel_card_limits", ["fuel_card_id"])

    op.create_table(
        "fuel_card_allowed_stations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fuel_card_id", sa.Integer(), sa.ForeignKey("fuel_cards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fuel_card_id", "station_id", name="uq_fuel_card_allowed_stations_card_station"),
    )
    op.create_index("ix_fuel_card_allowed_stations_card_station", "fuel_card_allowed_stations", ["fuel_card_id", "station_id"], unique=True)

    op.create_table(
        "fuel_card_allowed_fuel_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fuel_card_id", sa.Integer(), sa.ForeignKey("fuel_cards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fuel_type_id", sa.Integer(), sa.ForeignKey("fuel_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fuel_card_id", "fuel_type_id", name="uq_fuel_card_allowed_fuel_types_card_type"),
    )
    op.create_index("ix_fuel_card_allowed_fuel_types_card_type", "fuel_card_allowed_fuel_types", ["fuel_card_id", "fuel_type_id"], unique=True)

    op.create_table(
        "fuel_card_usage_windows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fuel_card_id", sa.Integer(), sa.ForeignKey("fuel_cards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_fuel_card_usage_windows_day_range"),
        sa.CheckConstraint("end_time > start_time", name="ck_fuel_card_usage_windows_time_range"),
    )
    op.create_index("ix_fuel_card_usage_windows_fuel_card_id", "fuel_card_usage_windows", ["fuel_card_id"])

    op.create_table(
        "fuel_prices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_id", sa.Integer(), sa.ForeignKey("stations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fuel_type_id", sa.Integer(), sa.ForeignKey("fuel_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("unit_price > 0", name="ck_fuel_prices_unit_price_positive"),
        sa.CheckConstraint("effective_until IS NULL OR effective_until >= effective_from", name="ck_fuel_prices_effectivity_range"),
    )
    op.create_index("ix_fuel_prices_station_id", "fuel_prices", ["station_id"])
    op.create_index("ix_fuel_prices_fuel_type_id", "fuel_prices", ["fuel_type_id"])
    op.create_index("ix_fuel_prices_created_by", "fuel_prices", ["created_by"])
    op.create_index("ix_fuel_prices_station_type_effective_from", "fuel_prices", ["station_id", "fuel_type_id", "effective_from"])

    for name in ("customer_id", "fleet_id", "fleet_group_id", "vehicle_id", "driver_id", "fuel_card_id", "nozzle_id"):
        op.add_column("sales", sa.Column(name, sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_sales_{name}", "sales", f"{name[:-3]}s" if name not in {"fleet_group_id", "fuel_card_id"} else {"fleet_group_id": "fleet_groups", "fuel_card_id": "fuel_cards"}[name], [name], ["id"], ondelete="RESTRICT")
        op.create_index(f"ix_sales_{name}", "sales", [name])

    op.add_column("sales", sa.Column("start_totalizer_liters", sa.Numeric(14, 3), nullable=True))
    op.add_column("sales", sa.Column("end_totalizer_liters", sa.Numeric(14, 3), nullable=True))
    op.add_column("sales", sa.Column("list_unit_price", sa.Numeric(14, 4), nullable=True))
    op.add_column("sales", sa.Column("discount_rate", sa.Numeric(5, 2), nullable=True))
    op.add_column("sales", sa.Column("authorization_failure_code", sa.String(length=100), nullable=True))
    op.add_column("sales", sa.Column("sale_status", sale_status, nullable=False, server_default=sa.text("'COMPLETED'::sale_status")))
    op.alter_column("sales", "sale_status", server_default=None)
    op.create_check_constraint("ck_sales_start_totalizer_nonnegative", "sales", "start_totalizer_liters IS NULL OR start_totalizer_liters >= 0")
    op.create_check_constraint("ck_sales_end_totalizer_nonnegative", "sales", "end_totalizer_liters IS NULL OR end_totalizer_liters >= 0")
    op.create_check_constraint("ck_sales_totalizer_order", "sales", "start_totalizer_liters IS NULL OR end_totalizer_liters IS NULL OR end_totalizer_liters >= start_totalizer_liters")
    op.create_check_constraint("ck_sales_discount_nonnegative", "sales", "discount_rate IS NULL OR discount_rate >= 0")
    op.create_check_constraint("ck_sales_discount_maximum", "sales", "discount_rate IS NULL OR discount_rate <= 100")
    for name in ("customer_id", "vehicle_id", "fuel_card_id", "nozzle_id"):
        op.create_index(f"ix_sales_{name}_timestamp", "sales", [name, "sale_timestamp"])


def downgrade() -> None:
    """Remove Stage 10 structures in reverse dependency order."""

    for name in ("customer_id", "vehicle_id", "fuel_card_id", "nozzle_id"):
        op.drop_index(f"ix_sales_{name}_timestamp", table_name="sales")
    for name in ("ck_sales_discount_maximum", "ck_sales_discount_nonnegative", "ck_sales_totalizer_order", "ck_sales_end_totalizer_nonnegative", "ck_sales_start_totalizer_nonnegative"):
        op.drop_constraint(name, "sales", type_="check")
    op.drop_column("sales", "sale_status")
    for name in ("authorization_failure_code", "discount_rate", "list_unit_price", "end_totalizer_liters", "start_totalizer_liters"):
        op.drop_column("sales", name)
    for name, table in reversed((
        ("customer_id", "customers"), ("fleet_id", "fleets"), ("fleet_group_id", "fleet_groups"), ("vehicle_id", "vehicles"), ("driver_id", "drivers"), ("fuel_card_id", "fuel_cards"), ("nozzle_id", "nozzles"),
    )):
        op.drop_index(f"ix_sales_{name}", table_name="sales")
        op.drop_constraint(f"fk_sales_{name}", "sales", type_="foreignkey")
        op.drop_column("sales", name)

    for index in ("ix_fuel_prices_station_type_effective_from", "ix_fuel_prices_created_by", "ix_fuel_prices_fuel_type_id", "ix_fuel_prices_station_id"):
        op.drop_index(index, table_name="fuel_prices")
    op.drop_table("fuel_prices")
    op.drop_index("ix_fuel_card_usage_windows_fuel_card_id", table_name="fuel_card_usage_windows")
    op.drop_table("fuel_card_usage_windows")
    op.drop_index("ix_fuel_card_allowed_fuel_types_card_type", table_name="fuel_card_allowed_fuel_types")
    op.drop_table("fuel_card_allowed_fuel_types")
    op.drop_index("ix_fuel_card_allowed_stations_card_station", table_name="fuel_card_allowed_stations")
    op.drop_table("fuel_card_allowed_stations")
    op.drop_index("ix_fuel_card_limits_fuel_card_id", table_name="fuel_card_limits")
    op.drop_table("fuel_card_limits")
    for index in ("ix_fuel_cards_unit_id", "ix_fuel_cards_card_code", "ix_fuel_cards_vehicle_id"):
        op.drop_index(index, table_name="fuel_cards")
    op.drop_table("fuel_cards")
    for index in ("ix_driver_vehicle_assignments_vehicle_id", "ix_driver_vehicle_assignments_driver_id"):
        op.drop_index(index, table_name="driver_vehicle_assignments")
    op.drop_table("driver_vehicle_assignments")
    op.drop_index("ix_drivers_reference_code", table_name="drivers")
    op.drop_table("drivers")
    for index in ("ix_vehicles_plate", "ix_vehicles_fleet_group_id"):
        op.drop_index(index, table_name="vehicles")
    op.drop_table("vehicles")
    op.drop_index("ix_fleet_groups_fleet_id", table_name="fleet_groups")
    op.drop_table("fleet_groups")
    op.drop_index("ix_fleets_customer_id", table_name="fleets")
    op.drop_table("fleets")
    op.drop_index("ix_customer_authorized_persons_customer_id", table_name="customer_authorized_persons")
    op.drop_table("customer_authorized_persons")
    for index in ("ix_customers_name", "ix_customers_code"):
        op.drop_index(index, table_name="customers")
    op.drop_table("customers")

    bind = op.get_bind()
    for name, values in reversed(ENUM_DEFINITIONS):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
