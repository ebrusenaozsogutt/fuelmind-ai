"""Leakage-safe daily demand datasets built from the Stage 12.1 raw loader.

This module is intentionally independent from the sensor/anomaly preprocessing
pipeline.  It prepares sales history only; it never trains or persists a model.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import isfinite
from typing import Iterable

import pandas as pd
from sqlalchemy.orm import Session

from app.ml.forecast_dataset_loader import ForecastRawDatasetLoader, ForecastRawSale
from app.utils.enums import AnomalyType, SaleStatus

TARGET_COLUMN = "daily_demand_liters"
IDENTIFIER_COLUMNS = ("date", "station_id", "fuel_type_id")
CALENDAR_FEATURE_COLUMNS = ("day_of_week", "day_of_month", "month", "is_weekend")
LAG_FEATURE_COLUMNS = ("lag_1", "lag_2", "lag_7", "lag_14")
ROLLING_FEATURE_COLUMNS = (
    "rolling_mean_3", "rolling_mean_7", "rolling_mean_14", "rolling_std_7",
)
FEATURE_COLUMNS = CALENDAR_FEATURE_COLUMNS + LAG_FEATURE_COLUMNS + ROLLING_FEATURE_COLUMNS
DIAGNOSTIC_COLUMNS = (
    "transaction_count", "daily_revenue", "average_sale_liters", "average_unit_price",
)
DAILY_DATASET_COLUMNS = IDENTIFIER_COLUMNS + (TARGET_COLUMN,) + DIAGNOSTIC_COLUMNS


@dataclass(frozen=True)
class DemandDatasetSummary:
    raw_sales: int
    valid_sales: int
    filtered_sales: int
    filtered_by_reason: dict[str, int]
    daily_rows: int
    model_ready_rows: int
    series_row_counts: dict[str, int]
    insufficient_history_series: tuple[str, ...]


@dataclass(frozen=True)
class DemandDatasetResult:
    """Both audit-friendly daily data and the warm-up-filtered model data."""

    daily_dataframe: pd.DataFrame
    feature_dataframe: pd.DataFrame
    summary: DemandDatasetSummary


class DemandForecastDatasetBuilder:
    """Turn completed raw sales into deterministic daily demand features."""

    def __init__(self, db: Session, *, business_timezone: str = "UTC") -> None:
        if business_timezone != "UTC":
            raise ValueError("FuelMind currently stores and groups forecast history in UTC.")
        self._loader = ForecastRawDatasetLoader(db)

    def build(
        self,
        *,
        station_id: int | None = None,
        start_at: date | datetime | None = None,
        end_at: date | datetime | None = None,
    ) -> DemandDatasetResult:
        return self.build_from_raw_sales(
            self._loader.load(station_id=station_id, start_at=start_at, end_at=end_at)
        )

    @classmethod
    def build_from_raw_sales(cls, raw_sales: Iterable[ForecastRawSale]) -> DemandDatasetResult:
        rows = list(raw_sales)
        accepted, reasons = cls._clean(rows)
        daily = cls._aggregate(accepted)
        featured = cls._features(daily)
        ready = featured.dropna(subset=list(LAG_FEATURE_COLUMNS + ROLLING_FEATURE_COLUMNS)).copy()
        ready = ready.sort_values(list(IDENTIFIER_COLUMNS), kind="stable").reset_index(drop=True)
        counts = cls._series_counts(daily)
        insufficient = tuple(key for key, count in counts.items() if count < 15)
        return DemandDatasetResult(
            daily_dataframe=daily,
            feature_dataframe=ready,
            summary=DemandDatasetSummary(
                raw_sales=len(rows), valid_sales=len(accepted), filtered_sales=len(rows) - len(accepted),
                filtered_by_reason=dict(sorted(reasons.items())), daily_rows=len(daily),
                model_ready_rows=len(ready), series_row_counts=counts,
                insufficient_history_series=insufficient,
            ),
        )

    @classmethod
    def _clean(cls, rows: list[ForecastRawSale]) -> tuple[list[ForecastRawSale], Counter[str]]:
        accepted: list[ForecastRawSale] = []
        reasons: Counter[str] = Counter()
        seen_simulation_ids: set[str] = set()
        for sale in rows:
            if sale.sale_status != SaleStatus.COMPLETED:
                reasons["not_completed"] += 1
            elif sale.station_id is None or sale.station_id <= 0:
                reasons["missing_station"] += 1
            elif sale.fuel_type_id is None or sale.fuel_type_id <= 0:
                reasons["missing_fuel_type"] += 1
            elif not isinstance(sale.sale_timestamp, datetime):
                reasons["invalid_timestamp"] += 1
            elif not cls._finite_positive(sale.quantity_liters):
                reasons["invalid_quantity"] += 1
            elif sale.anomaly_type == AnomalyType.DATA_QUALITY_ANOMALY:
                reasons["data_quality_anomaly"] += 1
            elif sale.simulation_sale_id and sale.simulation_sale_id in seen_simulation_ids:
                reasons["duplicate_simulation_sale_id"] += 1
            else:
                if sale.simulation_sale_id:
                    seen_simulation_ids.add(sale.simulation_sale_id)
                accepted.append(sale)
        return accepted, reasons

    @staticmethod
    def _finite_positive(value: object) -> bool:
        try:
            return isfinite(float(value)) and float(value) > 0
        except (TypeError, ValueError):
            return False

    @classmethod
    def _aggregate(cls, sales: list[ForecastRawSale]) -> pd.DataFrame:
        records = [
            {
                "date": cls._utc_date(sale.sale_timestamp), "station_id": sale.station_id,
                "fuel_type_id": sale.fuel_type_id, "quantity": float(sale.quantity_liters),
                "revenue": float(sale.total_amount), "unit_price": float(sale.unit_price),
            }
            for sale in sales
        ]
        if not records:
            return pd.DataFrame(columns=DAILY_DATASET_COLUMNS)
        frame = pd.DataFrame(records)
        daily = frame.groupby(list(IDENTIFIER_COLUMNS), as_index=False, sort=True).agg(
            daily_demand_liters=("quantity", "sum"), transaction_count=("quantity", "size"),
            daily_revenue=("revenue", "sum"), average_sale_liters=("quantity", "mean"),
            average_unit_price=("unit_price", "mean"),
        )
        filled: list[pd.DataFrame] = []
        for _, group in daily.groupby(["station_id", "fuel_type_id"], sort=True):
            group = group.sort_values("date", kind="stable")
            # A series is considered active between its first and last observed sale.
            # We do not invent zero demand before product activation or after retirement.
            days = pd.date_range(group["date"].min(), group["date"].max(), freq="D").date
            full = group.set_index("date").reindex(days).rename_axis("date").reset_index()
            full["station_id"] = int(group["station_id"].iloc[0])
            full["fuel_type_id"] = int(group["fuel_type_id"].iloc[0])
            for column in (TARGET_COLUMN, "transaction_count", "daily_revenue", "average_sale_liters", "average_unit_price"):
                full[column] = full[column].fillna(0.0)
            filled.append(full)
        return pd.concat(filled, ignore_index=True).sort_values(
            list(IDENTIFIER_COLUMNS), kind="stable"
        ).reset_index(drop=True)[list(DAILY_DATASET_COLUMNS)]

    @classmethod
    def _features(cls, daily: pd.DataFrame) -> pd.DataFrame:
        if daily.empty:
            return pd.DataFrame(columns=DAILY_DATASET_COLUMNS + FEATURE_COLUMNS)
        result = daily.copy()
        dates = pd.to_datetime(result["date"])
        result["day_of_week"] = dates.dt.dayofweek
        result["day_of_month"] = dates.dt.day
        result["month"] = dates.dt.month
        result["is_weekend"] = (result["day_of_week"] >= 5).astype(int)
        grouped = result.groupby(["station_id", "fuel_type_id"], sort=False)[TARGET_COLUMN]
        for lag in (1, 2, 7, 14):
            result[f"lag_{lag}"] = grouped.shift(lag)
        history = grouped.shift(1)
        keys = [result["station_id"], result["fuel_type_id"]]
        for window in (3, 7, 14):
            result[f"rolling_mean_{window}"] = history.groupby(keys, sort=False).transform(
                lambda values: values.rolling(window, min_periods=window).mean()
            )
        result["rolling_std_7"] = history.groupby(keys, sort=False).transform(
            lambda values: values.rolling(7, min_periods=7).std()
        )
        return result.sort_values(list(IDENTIFIER_COLUMNS), kind="stable").reset_index(drop=True)

    @staticmethod
    def _utc_date(value: datetime) -> date:
        # SQLite fixtures can materialize timezone-aware DB fields as naive UTC.
        instant = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return instant.date()

    @staticmethod
    def _series_counts(daily: pd.DataFrame) -> dict[str, int]:
        if daily.empty:
            return {}
        return {
            f"{station_id}:{fuel_type_id}": len(group)
            for (station_id, fuel_type_id), group in daily.groupby(["station_id", "fuel_type_id"], sort=True)
        }
