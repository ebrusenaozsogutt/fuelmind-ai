"""create_initial_fuelmind_schema

Revision ID: 20260804_0001
Revises:
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260804_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUM_DEFINITIONS = (
    ("user_role", ("ADMIN", "OPERATOR")),
    ("sensor_status", ("ACTIVE", "WARNING", "FAULT", "OFFLINE")),
    ("pump_status", ("ACTIVE", "IDLE", "MAINTENANCE", "FAULT", "OFFLINE")),
    (
        "anomaly_type",
        (
            "SENSOR_ANOMALY",
            "EQUIPMENT_ANOMALY",
            "TRANSACTION_ANOMALY",
            "DEMAND_ANOMALY",
            "DATA_QUALITY_ANOMALY",
        ),
    ),
    ("alarm_severity", ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")),
    (
        "alarm_status",
        ("NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"),
    ),
    ("recommendation_priority", ("LOW", "MEDIUM", "HIGH", "CRITICAL")),
    ("recommendation_status", ("NEW", "APPROVED", "REJECTED", "COMPLETED")),
    ("simulation_target_type", ("STATION", "TANK", "PUMP")),
    (
        "simulation_status",
        ("CREATED", "RUNNING", "PAUSED", "COMPLETED", "STOPPED", "FAILED"),
    ),
)


def enum_column(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    """Return a column enum that does not independently create its DB type."""

    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    """Create the initial FuelMind AI PostgreSQL schema."""

    bind = op.get_bind()
    for name, values in ENUM_DEFINITIONS:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    user_role = enum_column("user_role", ("ADMIN", "OPERATOR"))
    sensor_status = enum_column(
        "sensor_status", ("ACTIVE", "WARNING", "FAULT", "OFFLINE")
    )
    pump_status = enum_column(
        "pump_status", ("ACTIVE", "IDLE", "MAINTENANCE", "FAULT", "OFFLINE")
    )
    anomaly_type = enum_column(
        "anomaly_type",
        (
            "SENSOR_ANOMALY",
            "EQUIPMENT_ANOMALY",
            "TRANSACTION_ANOMALY",
            "DEMAND_ANOMALY",
            "DATA_QUALITY_ANOMALY",
        ),
    )
    alarm_severity = enum_column(
        "alarm_severity", ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")
    )
    alarm_status = enum_column(
        "alarm_status",
        ("NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"),
    )
    recommendation_priority = enum_column(
        "recommendation_priority", ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    )
    recommendation_status = enum_column(
        "recommendation_status", ("NEW", "APPROVED", "REJECTED", "COMPLETED")
    )
    simulation_target_type = enum_column(
        "simulation_target_type", ("STATION", "TANK", "PUMP")
    )
    simulation_status = enum_column(
        "simulation_status",
        ("CREATED", "RUNNING", "PAUSED", "COMPLETED", "STOPPED", "FAILED"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table(
        "stations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_stations_code"),
    )
    op.create_index("ix_stations_code", "stations", ["code"], unique=True)
    op.create_index("ix_stations_name", "stations", ["name"])
    op.create_index("ix_stations_city", "stations", ["city"])
    op.create_index("ix_stations_district", "stations", ["district"])
    op.create_table(
        "fuel_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("code", name="uq_fuel_types_code"),
    )
    op.create_index("ix_fuel_types_code", "fuel_types", ["code"], unique=True)
    op.create_table(
        "tanks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "fuel_type_id",
            sa.Integer(),
            sa.ForeignKey("fuel_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("capacity_liters", sa.Numeric(14, 3), nullable=False),
        sa.Column("current_level_liters", sa.Numeric(14, 3), nullable=False),
        sa.Column("minimum_safe_level", sa.Numeric(14, 3), nullable=False),
        sa.Column("critical_level", sa.Numeric(14, 3), nullable=False),
        sa.Column("water_level", sa.Numeric(14, 3), nullable=False),
        sa.Column("temperature", sa.Numeric(6, 2)),
        sa.Column("sensor_status", sensor_status, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("station_id", "code", name="uq_tanks_station_code"),
        sa.CheckConstraint("capacity_liters > 0", name="ck_tanks_capacity_positive"),
        sa.CheckConstraint(
            "current_level_liters >= 0", name="ck_tanks_current_level_nonnegative"
        ),
        sa.CheckConstraint(
            "minimum_safe_level >= 0", name="ck_tanks_min_safe_nonnegative"
        ),
        sa.CheckConstraint("critical_level >= 0", name="ck_tanks_critical_nonnegative"),
        sa.CheckConstraint(
            "current_level_liters <= capacity_liters",
            name="ck_tanks_current_level_within_capacity",
        ),
        sa.CheckConstraint(
            "minimum_safe_level <= capacity_liters",
            name="ck_tanks_min_safe_within_capacity",
        ),
        sa.CheckConstraint(
            "critical_level <= capacity_liters",
            name="ck_tanks_critical_within_capacity",
        ),
        sa.CheckConstraint("water_level >= 0", name="ck_tanks_water_level_nonnegative"),
    )
    op.create_index("ix_tanks_station_id", "tanks", ["station_id"])
    op.create_index("ix_tanks_fuel_type_id", "tanks", ["fuel_type_id"])
    op.create_table(
        "pumps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tank_id",
            sa.Integer(),
            sa.ForeignKey("tanks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("status", pump_status, nullable=False),
        sa.Column("nominal_flow_rate", sa.Numeric(12, 3), nullable=False),
        sa.Column("minimum_flow_rate", sa.Numeric(12, 3), nullable=False),
        sa.Column("maximum_motor_current", sa.Numeric(12, 3), nullable=False),
        sa.Column("maximum_pressure", sa.Numeric(12, 3), nullable=False),
        sa.Column("last_maintenance_at", sa.DateTime(timezone=True)),
        sa.Column("total_working_hours", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("station_id", "code", name="uq_pumps_station_code"),
        sa.CheckConstraint(
            "nominal_flow_rate > 0", name="ck_pumps_nominal_flow_positive"
        ),
        sa.CheckConstraint(
            "minimum_flow_rate >= 0", name="ck_pumps_min_flow_nonnegative"
        ),
        sa.CheckConstraint(
            "minimum_flow_rate <= nominal_flow_rate",
            name="ck_pumps_min_flow_within_nominal",
        ),
        sa.CheckConstraint(
            "maximum_motor_current > 0", name="ck_pumps_motor_current_positive"
        ),
        sa.CheckConstraint("maximum_pressure > 0", name="ck_pumps_pressure_positive"),
        sa.CheckConstraint(
            "total_working_hours >= 0", name="ck_pumps_working_hours_nonnegative"
        ),
    )
    op.create_index("ix_pumps_station_id", "pumps", ["station_id"])
    op.create_index("ix_pumps_tank_id", "pumps", ["tank_id"])
    op.create_table(
        "sales",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tank_id",
            sa.Integer(),
            sa.ForeignKey("tanks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "pump_id",
            sa.Integer(),
            sa.ForeignKey("pumps.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "fuel_type_id",
            sa.Integer(),
            sa.ForeignKey("fuel_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sale_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity_liters", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("level_before", sa.Numeric(14, 3), nullable=False),
        sa.Column("level_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("anomaly_score", sa.Numeric(5, 2)),
        sa.Column("anomaly_type", anomaly_type),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_liters > 0", name="ck_sales_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_sales_unit_price_nonnegative"),
        sa.CheckConstraint(
            "total_amount >= 0", name="ck_sales_total_amount_nonnegative"
        ),
        sa.CheckConstraint(
            "duration_seconds >= 0", name="ck_sales_duration_nonnegative"
        ),
        sa.CheckConstraint(
            "level_before >= 0", name="ck_sales_level_before_nonnegative"
        ),
        sa.CheckConstraint("level_after >= 0", name="ck_sales_level_after_nonnegative"),
        sa.CheckConstraint(
            "anomaly_score IS NULL OR anomaly_score BETWEEN 0 AND 100",
            name="ck_sales_anomaly_score_range",
        ),
    )
    for column in (
        "station_id",
        "tank_id",
        "pump_id",
        "fuel_type_id",
        "sale_timestamp",
    ):
        op.create_index(f"ix_sales_{column}", "sales", [column])
    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tank_id", sa.Integer(), sa.ForeignKey("tanks.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "pump_id", sa.Integer(), sa.ForeignKey("pumps.id", ondelete="RESTRICT")
        ),
        sa.Column("reading_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tank_level", sa.Numeric(14, 3)),
        sa.Column("temperature", sa.Numeric(6, 2)),
        sa.Column("water_level", sa.Numeric(14, 3)),
        sa.Column("flow_rate", sa.Numeric(12, 3)),
        sa.Column("pressure", sa.Numeric(12, 3)),
        sa.Column("motor_current", sa.Numeric(12, 3)),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("working_duration", sa.Numeric(14, 2)),
        sa.Column("data_quality_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("anomaly_score", sa.Numeric(5, 2)),
        sa.Column("anomaly_type", anomaly_type),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tank_id IS NOT NULL OR pump_id IS NOT NULL",
            name="ck_sensor_readings_target_present",
        ),
        sa.CheckConstraint(
            "tank_level IS NULL OR tank_level >= 0",
            name="ck_sensor_readings_tank_level_nonnegative",
        ),
        sa.CheckConstraint(
            "water_level IS NULL OR water_level >= 0",
            name="ck_sensor_readings_water_level_nonnegative",
        ),
        sa.CheckConstraint(
            "flow_rate IS NULL OR flow_rate >= 0",
            name="ck_sensor_readings_flow_rate_nonnegative",
        ),
        sa.CheckConstraint(
            "pressure IS NULL OR pressure >= 0",
            name="ck_sensor_readings_pressure_nonnegative",
        ),
        sa.CheckConstraint(
            "motor_current IS NULL OR motor_current >= 0",
            name="ck_sensor_readings_motor_current_nonnegative",
        ),
        sa.CheckConstraint(
            "working_duration IS NULL OR working_duration >= 0",
            name="ck_sensor_readings_working_duration_nonnegative",
        ),
        sa.CheckConstraint(
            "error_count >= 0", name="ck_sensor_readings_error_count_nonnegative"
        ),
        sa.CheckConstraint(
            "data_quality_score BETWEEN 0 AND 100",
            name="ck_sensor_readings_quality_score_range",
        ),
        sa.CheckConstraint(
            "anomaly_score IS NULL OR anomaly_score BETWEEN 0 AND 100",
            name="ck_sensor_readings_anomaly_score_range",
        ),
    )
    for column in ("station_id", "tank_id", "pump_id", "reading_timestamp"):
        op.create_index(f"ix_sensor_readings_{column}", "sensor_readings", [column])
    op.create_index(
        "ix_sensor_readings_station_timestamp",
        "sensor_readings",
        ["station_id", "reading_timestamp"],
    )
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tank_id",
            sa.Integer(),
            sa.ForeignKey("tanks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("delivery_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity_liters", sa.Numeric(14, 3), nullable=False),
        sa.Column("level_before", sa.Numeric(14, 3), nullable=False),
        sa.Column("level_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("supplier_name", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity_liters > 0", name="ck_deliveries_quantity_positive"
        ),
        sa.CheckConstraint(
            "level_before >= 0", name="ck_deliveries_level_before_nonnegative"
        ),
        sa.CheckConstraint(
            "level_after >= 0", name="ck_deliveries_level_after_nonnegative"
        ),
        sa.CheckConstraint(
            "level_after >= level_before", name="ck_deliveries_level_increases"
        ),
    )
    op.create_index("ix_deliveries_tank_id", "deliveries", ["tank_id"])
    op.create_index(
        "ix_deliveries_delivery_timestamp", "deliveries", ["delivery_timestamp"]
    )
    op.create_table(
        "alarms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tank_id", sa.Integer(), sa.ForeignKey("tanks.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "pump_id", sa.Integer(), sa.ForeignKey("pumps.id", ondelete="RESTRICT")
        ),
        sa.Column("alarm_type", sa.String(length=100), nullable=False),
        sa.Column("severity", alarm_severity, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("probable_causes", postgresql.JSONB()),
        sa.Column("recommended_action", sa.Text()),
        sa.Column("anomaly_score", sa.Numeric(5, 2)),
        sa.Column("status", alarm_status, nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "resolved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT")
        ),
        sa.Column("resolution_note", sa.Text()),
        sa.CheckConstraint(
            "anomaly_score IS NULL OR anomaly_score BETWEEN 0 AND 100",
            name="ck_alarms_anomaly_score_range",
        ),
    )
    for column in (
        "station_id",
        "tank_id",
        "pump_id",
        "alarm_type",
        "detected_at",
        "resolved_by",
    ):
        op.create_index(f"ix_alarms_{column}", "alarms", [column])
    op.create_table(
        "forecasts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "fuel_type_id",
            sa.Integer(),
            sa.ForeignKey("fuel_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("predicted_demand", sa.Numeric(14, 3), nullable=False),
        sa.Column("lower_bound", sa.Numeric(14, 3), nullable=False),
        sa.Column("upper_bound", sa.Numeric(14, 3), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "station_id",
            "fuel_type_id",
            "forecast_date",
            "model_version",
            name="uq_forecasts_station_fuel_date_model",
        ),
        sa.CheckConstraint(
            "predicted_demand >= 0", name="ck_forecasts_predicted_demand_nonnegative"
        ),
        sa.CheckConstraint(
            "lower_bound >= 0", name="ck_forecasts_lower_bound_nonnegative"
        ),
        sa.CheckConstraint(
            "upper_bound >= 0", name="ck_forecasts_upper_bound_nonnegative"
        ),
        sa.CheckConstraint(
            "lower_bound <= predicted_demand",
            name="ck_forecasts_lower_within_prediction",
        ),
        sa.CheckConstraint(
            "predicted_demand <= upper_bound",
            name="ck_forecasts_prediction_within_upper",
        ),
        sa.CheckConstraint(
            "confidence_score BETWEEN 0 AND 100",
            name="ck_forecasts_confidence_score_range",
        ),
    )
    for column in ("station_id", "fuel_type_id", "forecast_date"):
        op.create_index(f"ix_forecasts_{column}", "forecasts", [column])
    op.create_table(
        "order_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tank_id",
            sa.Integer(),
            sa.ForeignKey("tanks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recommended_order_date", sa.Date(), nullable=False),
        sa.Column("recommended_delivery_date", sa.Date(), nullable=False),
        sa.Column("recommended_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("critical_stock_date", sa.Date()),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("priority", recommendation_priority, nullable=False),
        sa.Column("status", recommendation_status, nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "recommended_quantity >= 0",
            name="ck_order_recommendations_quantity_nonnegative",
        ),
        sa.CheckConstraint(
            "confidence_score BETWEEN 0 AND 100",
            name="ck_order_recommendations_confidence_score_range",
        ),
        sa.CheckConstraint(
            "recommended_delivery_date >= recommended_order_date",
            name="ck_order_recommendations_delivery_after_order",
        ),
    )
    op.create_index(
        "ix_order_recommendations_station_id", "order_recommendations", ["station_id"]
    )
    op.create_index(
        "ix_order_recommendations_tank_id", "order_recommendations", ["tank_id"]
    )
    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_type", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("training_start_date", sa.Date(), nullable=False),
        sa.Column("training_end_date", sa.Date(), nullable=False),
        sa.Column("training_row_count", sa.Integer(), nullable=False),
        sa.Column("mae", sa.Numeric(14, 6)),
        sa.Column("rmse", sa.Numeric(14, 6)),
        sa.Column("mape", sa.Numeric(8, 4)),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "model_type", "version", name="uq_model_versions_type_version"
        ),
        sa.CheckConstraint(
            "training_row_count >= 0", name="ck_model_versions_row_count_nonnegative"
        ),
        sa.CheckConstraint(
            "mae IS NULL OR mae >= 0", name="ck_model_versions_mae_nonnegative"
        ),
        sa.CheckConstraint(
            "rmse IS NULL OR rmse >= 0", name="ck_model_versions_rmse_nonnegative"
        ),
        sa.CheckConstraint(
            "mape IS NULL OR mape >= 0", name="ck_model_versions_mape_nonnegative"
        ),
    )
    op.create_index("ix_model_versions_model_type", "model_versions", ["model_type"])
    op.create_table(
        "simulation_scenarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("scenario_type", sa.String(length=100), nullable=False),
        sa.Column("target_type", simulation_target_type, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("parameters_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", simulation_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "duration_minutes > 0", name="ck_simulation_scenarios_duration_positive"
        ),
    )
    for column in ("name", "scenario_type", "target_id"):
        op.create_index(
            f"ix_simulation_scenarios_{column}", "simulation_scenarios", [column]
        )


def downgrade() -> None:
    """Drop tables in dependency order, then shared PostgreSQL enum types."""

    for table_name in (
        "simulation_scenarios",
        "model_versions",
        "order_recommendations",
        "forecasts",
        "alarms",
        "deliveries",
        "sensor_readings",
        "sales",
        "pumps",
        "tanks",
        "fuel_types",
        "stations",
        "users",
    ):
        op.drop_table(table_name)

    bind = op.get_bind()
    for name, values in reversed(ENUM_DEFINITIONS):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
