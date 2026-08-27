"""Read-only tank stock reconciliation contracts."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class TankReconciliationRequest(BaseModel):
    """Measured opening and closing levels for a bounded reconciliation period."""

    period_start: datetime
    period_end: datetime
    opening_level_liters: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    actual_closing_level_liters: Decimal = Field(
        ge=0, max_digits=14, decimal_places=3
    )

    @model_validator(mode="after")
    def validate_period(self) -> "TankReconciliationRequest":
        if self.period_start.tzinfo is None or self.period_start.utcoffset() is None:
            raise ValueError("period_start must include a timezone.")
        if self.period_end.tzinfo is None or self.period_end.utcoffset() is None:
            raise ValueError("period_end must include a timezone.")
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be after period_start.")
        return self


class TankReconciliationRead(BaseModel):
    tank_id: int
    period_start: datetime
    period_end: datetime
    opening_level_liters: Decimal
    completed_sales_liters: Decimal
    delivery_liters: Decimal
    expected_closing_level_liters: Decimal
    actual_closing_level_liters: Decimal
    difference_liters: Decimal
    difference_percent: Decimal
    is_reconciled: bool
