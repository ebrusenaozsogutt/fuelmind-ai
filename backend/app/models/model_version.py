"""Machine learning model version database model."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.datetime_utils import utc_now


class ModelVersion(Base):
    """Metadata for a trained machine learning model artifact."""

    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint(
            "model_type", "version", name="uq_model_versions_type_version"
        ),
        CheckConstraint(
            "training_row_count >= 0", name="ck_model_versions_row_count_nonnegative"
        ),
        CheckConstraint(
            "mae IS NULL OR mae >= 0", name="ck_model_versions_mae_nonnegative"
        ),
        CheckConstraint(
            "rmse IS NULL OR rmse >= 0", name="ck_model_versions_rmse_nonnegative"
        ),
        CheckConstraint(
            "mape IS NULL OR mape >= 0", name="ck_model_versions_mape_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    training_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    training_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    training_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mae: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    rmse: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    mape: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
