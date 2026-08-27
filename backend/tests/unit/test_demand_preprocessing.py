"""Acceptance coverage for Stage 12.2-12.3 demand preprocessing."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
import pytest

from app.ml.demand_preprocessing import DemandForecastDatasetBuilder
from app.ml.forecast_dataset_loader import ForecastRawSale
from app.utils.enums import AnomalyType, SaleStatus


def sale(
    sale_id: int,
    day: int,
    quantity: str = "10",
    *,
    station_id: int = 1,
    fuel_type_id: int = 1,
    timestamp: datetime | None = None,
    status: SaleStatus = SaleStatus.COMPLETED,
    simulation_sale_id: str | None = None,
    anomaly_type: AnomalyType | None = None,
) -> ForecastRawSale:
    amount = Decimal(quantity) * Decimal("2")
    return ForecastRawSale(
        sale_id=sale_id, simulation_sale_id=simulation_sale_id, simulation_run_id=None,
        station_id=station_id, tank_id=1, pump_id=1, nozzle_id=None, fuel_type_id=fuel_type_id,
        customer_id=None, vehicle_id=None, fuel_card_id=None, attendant_id=None, shift_id=None,
        sale_timestamp=timestamp or datetime(2026, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=day),
        quantity_liters=Decimal(quantity), unit_price=Decimal("2"), total_amount=amount,
        start_totalizer_liters=None, end_totalizer_liters=None, payment_type=None,
        sale_status=status, is_anomaly=anomaly_type is not None, anomaly_type=anomaly_type,
    )


def linear_sales(days: int = 20, *, station_id: int = 1, fuel_type_id: int = 1) -> list[ForecastRawSale]:
    return [sale(index + 1, index, str((index + 1) * 10), station_id=station_id, fuel_type_id=fuel_type_id) for index in range(days)]


def test_daily_aggregation_keeps_station_and_fuel_series_separate() -> None:
    result = DemandForecastDatasetBuilder.build_from_raw_sales([
        sale(1, 0, "40"), sale(2, 0, "30"), sale(3, 0, "50"),
        sale(4, 0, "20", fuel_type_id=2), sale(5, 0, "25", station_id=2),
    ])
    rows = result.daily_dataframe.set_index(["station_id", "fuel_type_id"])
    assert rows.loc[(1, 1), "daily_demand_liters"] == 120
    assert rows.loc[(1, 1), "transaction_count"] == 3
    assert rows.loc[(1, 2), "daily_demand_liters"] == 20
    assert rows.loc[(2, 1), "daily_demand_liters"] == 25


def test_cleaning_excludes_invalid_and_duplicate_but_keeps_real_demand_anomaly() -> None:
    valid = sale(1, 0, "10", simulation_sale_id="once")
    result = DemandForecastDatasetBuilder.build_from_raw_sales([
        valid, sale(2, 0, "10", simulation_sale_id="once"), sale(3, 0, "10", status=SaleStatus.CANCELLED),
        sale(4, 0, "-1"), sale(5, 0, "25", anomaly_type=AnomalyType.DEMAND_ANOMALY),
        sale(6, 0, "5", anomaly_type=AnomalyType.DATA_QUALITY_ANOMALY),
    ])
    assert result.summary.valid_sales == 2
    assert result.summary.filtered_by_reason == {
        "data_quality_anomaly": 1, "duplicate_simulation_sale_id": 1,
        "invalid_quantity": 1, "not_completed": 1,
    }
    assert result.daily_dataframe.iloc[0].daily_demand_liters == 35


def test_missing_active_day_is_zero_and_features_are_leakage_safe() -> None:
    rows = [sale(index + 1, index, str(index + 1)) for index in range(20) if index != 5]
    result = DemandForecastDatasetBuilder.build_from_raw_sales(rows)
    daily = result.daily_dataframe
    assert daily.loc[daily.date.astype(str) == "2026-01-06", "daily_demand_liters"].iloc[0] == 0
    featured = result.feature_dataframe.set_index("date")
    row = featured.loc[datetime(2026, 1, 15).date()]
    assert row.lag_1 == 14
    assert row.lag_2 == 13
    assert row.lag_7 == 8
    assert row.lag_14 == 1
    assert row.rolling_mean_3 == (12 + 13 + 14) / 3
    assert row.rolling_mean_7 == sum(range(8, 15)) / 7
    assert row.rolling_std_7 == pytest.approx(pd.Series(range(8, 15), dtype=float).std())


def test_series_are_isolated_and_warmup_rows_are_not_model_ready() -> None:
    result = DemandForecastDatasetBuilder.build_from_raw_sales(
        linear_sales() + linear_sales(station_id=2)
    )
    assert result.summary.daily_rows == 40
    assert result.summary.model_ready_rows == 12
    first_station_two = result.feature_dataframe[result.feature_dataframe.station_id == 2].iloc[0]
    assert first_station_two.date == datetime(2026, 1, 15).date()
    assert first_station_two.lag_14 == 10


def test_utc_day_grouping_and_output_are_deterministic() -> None:
    rows = [
        sale(1, 0, "10", timestamp=datetime(2026, 1, 1, 23, 30, tzinfo=timezone.utc)),
        sale(2, 0, "20", timestamp=datetime(2026, 1, 2, 0, 30, tzinfo=timezone.utc)),
    ]
    first = DemandForecastDatasetBuilder.build_from_raw_sales(rows)
    second = DemandForecastDatasetBuilder.build_from_raw_sales(list(reversed(rows)))
    assert first.daily_dataframe.date.tolist() == [datetime(2026, 1, 1).date(), datetime(2026, 1, 2).date()]
    pd.testing.assert_frame_equal(first.daily_dataframe, second.daily_dataframe)
    pd.testing.assert_frame_equal(first.feature_dataframe, second.feature_dataframe)
