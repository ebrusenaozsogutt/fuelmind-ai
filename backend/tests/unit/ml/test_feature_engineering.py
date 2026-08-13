"""Unit coverage for leakage-safe Stage 8.2 feature engineering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.ml.feature_engineering import (
    AnomalyFeatureEngineer,
    PUMP_ANOMALY_FEATURE_NAMES,
    TANK_ANOMALY_FEATURE_NAMES,
)


START = datetime(2026, 1, 5, 10, tzinfo=timezone.utc)  # Monday


def _pump_rows(*, pump_id: int = 1, station_id: int = 1, times: list[int] | None = None) -> list[dict[str, object]]:
    minutes = times or [0, 5, 10, 15, 20, 25, 30]
    return [
        {
            "reading_timestamp": START + timedelta(minutes=minute), "station_id": station_id,
            "pump_id": pump_id, "tank_id": 10 + pump_id, "simulation_run_id": 1,
            "sequence_number": index + 1, "source_type": "SIMULATION",
            "flow_rate": 10 + index, "pressure": 2 + index * 2, "motor_current": 9 + index,
            "pump_temperature": 25 + index, "error_count": index, "working_duration": index / 12,
            "data_quality_score": 95, "tank_level": np.nan, "true_tank_level": np.nan,
            "temperature": np.nan, "water_level": np.nan,
        }
        for index, minute in enumerate(minutes)
    ]


def _tank_rows(*, tank_id: int = 11, station_id: int = 1) -> list[dict[str, object]]:
    return [
        {
            "reading_timestamp": START + timedelta(minutes=index * 5), "station_id": station_id,
            "pump_id": np.nan, "tank_id": tank_id, "simulation_run_id": 1,
            "sequence_number": index + 1, "source_type": "SIMULATION",
            "tank_level": 500 - index * 3, "true_tank_level": 501 - index * 3,
            "temperature": 20 + index, "water_level": 1 + index / 10, "error_count": index,
            "data_quality_score": 95, "flow_rate": np.nan, "pressure": np.nan,
            "motor_current": np.nan, "pump_temperature": np.nan, "working_duration": np.nan,
        }
        for index in range(7)
    ]


def _result(rows: list[dict[str, object]]):
    return AnomalyFeatureEngineer().engineer(pd.DataFrame(rows))


def test_feature_names_are_deterministic_and_time_context_is_correct() -> None:
    result = _result(_pump_rows() + _tank_rows())

    assert result.feature_names["pump"] == PUMP_ANOMALY_FEATURE_NAMES
    assert result.feature_names["tank"] == TANK_ANOMALY_FEATURE_NAMES
    assert result.features["pump"].columns.tolist() == list(PUMP_ANOMALY_FEATURE_NAMES)
    assert result.features["pump"].iloc[0]["hour_of_day"] == 10
    assert result.features["pump"].iloc[0]["day_of_week"] == 0
    assert result.features["pump"].iloc[0]["is_weekend"] == 0


def test_entity_deltas_do_not_mix_pumps_or_tanks_and_are_chronological() -> None:
    rows = _pump_rows(pump_id=1) + _pump_rows(pump_id=2) + _tank_rows(tank_id=11) + _tank_rows(tank_id=12)
    for row in rows:
        if row["pump_id"] == 2:
            row["motor_current"] = float(row["motor_current"]) + 100
        if row["tank_id"] == 12 and pd.isna(row["pump_id"]):
            row["tank_level"] = float(row["tank_level"]) + 100
    result = _result(list(reversed(rows)))

    pump_metadata = result.metadata["pump"]
    pump_features = result.features["pump"]
    pump_one = pump_features[pump_metadata["pump_id"].eq(1)].iloc[0]
    pump_two = pump_features[pump_metadata["pump_id"].eq(2)].iloc[0]
    tank_metadata = result.metadata["tank"]
    tank_features = result.features["tank"]
    tank_one = tank_features[tank_metadata["tank_id"].eq(11)].iloc[0]
    tank_two = tank_features[tank_metadata["tank_id"].eq(12)].iloc[0]

    assert pump_one["motor_current_change"] == 1
    assert pump_two["motor_current_change"] == 1
    assert tank_one["tank_level_change"] == -3
    assert tank_two["tank_level_change"] == -3
    assert pump_metadata["reading_timestamp"].is_monotonic_increasing
    assert tank_metadata["reading_timestamp"].is_monotonic_increasing


def test_deltas_and_trailing_rolling_features_use_only_past_and_current_data() -> None:
    rows = _pump_rows()
    result = _result(rows)
    features = result.features["pump"].iloc[0]

    assert features["flow_rate_change"] == 1
    assert features["motor_current_change"] == 1
    assert features["flow_rate_change_5min"] == 1
    assert features["motor_current_change_5min"] == 1
    assert features["average_flow_rate_30min"] == 13
    assert np.isclose(features["pressure_std_30min"], pd.Series([2, 4, 6, 8, 10, 12, 14]).std())
    assert features["pump_temperature_change_30min"] == 6

    future_rows = rows + _pump_rows(times=[35])
    future_rows[-1]["flow_rate"] = 1000
    with_future = _result(future_rows)
    at_thirty = with_future.features["pump"].loc[
        with_future.metadata["pump"]["reading_timestamp"].eq(pd.Timestamp(START + timedelta(minutes=30)))
    ].iloc[0]
    assert at_thirty["average_flow_rate_30min"] == 13


def test_time_based_windows_handle_irregular_sampling() -> None:
    result = _result(_pump_rows(times=[0, 7, 14, 21, 30]))
    features = result.features["pump"].iloc[0]

    assert features["flow_rate_change_5min"] == 1
    assert features["average_flow_rate_30min"] == 12


def test_nan_infinity_and_historyless_rows_are_dropped_safely() -> None:
    rows = _pump_rows()
    rows[-1]["pressure"] = np.inf
    result = _result(rows)

    assert result.features["pump"].empty
    assert result.summary.dropped_rows_non_finite >= 1
    assert result.summary.dropped_rows_missing_history_or_values >= 1


def test_same_input_produces_same_features_and_tank_changes() -> None:
    rows = _pump_rows() + _tank_rows()
    one = _result(rows)
    two = _result(rows)

    pd.testing.assert_frame_equal(one.features["pump"], two.features["pump"])
    pd.testing.assert_frame_equal(one.features["tank"], two.features["tank"])
    tank = one.features["tank"].iloc[0]
    assert tank["temperature_change_30min"] == 6
    assert np.isclose(tank["water_level_change_30min"], 0.6)
