"""Add anomaly model-registry metadata and active-model invariant.

Revision ID: 20260812_0009
Revises: 20260810_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0009"
down_revision: str | None = "20260810_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_versions",
        sa.Column("model_family", sa.String(length=50), nullable=False, server_default="default"),
    )
    op.add_column(
        "model_versions",
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "model_versions",
        sa.Column("artifact_size_bytes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "model_versions",
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.alter_column("model_versions", "model_family", server_default=None)
    op.alter_column("model_versions", "artifact_sha256", server_default=None)
    op.alter_column("model_versions", "artifact_size_bytes", server_default=None)
    op.alter_column("model_versions", "metadata_json", server_default=None)
    op.create_index(
        "ix_model_versions_model_family", "model_versions", ["model_family"]
    )
    op.create_check_constraint(
        "ck_model_versions_artifact_size_nonnegative",
        "model_versions",
        "artifact_size_bytes >= 0",
    )
    # The legacy schema defaulted every row to active. Keep the newest row in
    # each type/family before adding the partial uniqueness invariant.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY model_type, model_family
                       ORDER BY trained_at DESC, id DESC
                   ) AS position
            FROM model_versions
            WHERE is_active IS TRUE
        )
        UPDATE model_versions
        SET is_active = FALSE
        FROM ranked
        WHERE model_versions.id = ranked.id AND ranked.position > 1
        """
    )
    op.create_index(
        "uq_model_versions_one_active_family",
        "model_versions",
        ["model_type", "model_family"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index("uq_model_versions_one_active_family", table_name="model_versions")
    op.drop_constraint(
        "ck_model_versions_artifact_size_nonnegative",
        "model_versions",
        type_="check",
    )
    op.drop_index("ix_model_versions_model_family", table_name="model_versions")
    op.drop_column("model_versions", "metadata_json")
    op.drop_column("model_versions", "artifact_size_bytes")
    op.drop_column("model_versions", "artifact_sha256")
    op.drop_column("model_versions", "model_family")
