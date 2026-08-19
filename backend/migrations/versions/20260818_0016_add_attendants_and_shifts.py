"""Add station attendants, shifts, assignments, and nullable sale snapshots."""

from alembic import op
import sqlalchemy as sa

revision = "20260818_0016"
down_revision = "20260817_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "attendants",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "station_id",
            sa.Integer,
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("employee_number", sa.String(64), nullable=False),
        sa.Column("phone", sa.String(32)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("station_id", "code", name="uq_attendants_station_code"),
        sa.UniqueConstraint("employee_number", name="uq_attendants_employee_number"),
    )
    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "station_id",
            sa.Integer,
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("station_id", "code", name="uq_shifts_station_code"),
    )
    op.create_table(
        "attendant_shift_assignments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "attendant_id",
            sa.Integer,
            sa.ForeignKey("attendants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "shift_id",
            sa.Integer,
            sa.ForeignKey("shifts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "station_id",
            sa.Integer,
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "attendant_id", "shift_id", name="uq_attendant_shift_assignment"
        ),
    )
    op.add_column(
        "sales",
        sa.Column(
            "attendant_id",
            sa.Integer,
            sa.ForeignKey("attendants.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "sales",
        sa.Column(
            "shift_id",
            sa.Integer,
            sa.ForeignKey("shifts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("sales", "shift_id")
    op.drop_column("sales", "attendant_id")
    op.drop_table("attendant_shift_assignments")
    op.drop_table("shifts")
    op.drop_table("attendants")
