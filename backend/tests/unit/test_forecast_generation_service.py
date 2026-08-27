"""Unit contracts for production recursive demand forecasts."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.ml.demand_preprocessing import FEATURE_COLUMNS
from app.services.forecast_generation_service import ForecastGenerationService


class CapturingModel:
    def __init__(self, predictions: list[float]) -> None:
        self.predictions = iter(predictions)
        self.features = []

    def predict(self, frame):
        self.features.append(frame.copy())
        return [next(self.predictions)]


class EmptySession:
    def add(self, _row) -> None:
        pass

    def scalar(self, _statement):
        return None


def record(*, mae: float = 10, rows: int = 100, trained_at: datetime | None = None):
    return SimpleNamespace(
        version="v0001", mae=mae, training_row_count=rows,
        trained_at=trained_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata_json={"residual_abs_p90": 20.0},
    )


def test_recursive_features_keep_contract_and_use_prior_prediction() -> None:
    service = ForecastGenerationService(EmptySession())
    model = CapturingModel([101, 102, 103, 104, 105, 106, 107])
    history = [float(value) for value in range(1, 21)]
    rows = service._generate_series(record(), model, 1, 1, date(2026, 1, 20), history)

    assert len(rows) == 7
    assert [row.forecast_date for row in rows] == [date(2026, 1, 20) + timedelta(days=value) for value in range(1, 8)]
    assert model.features[0].columns.tolist() == list(FEATURE_COLUMNS)
    assert model.features[1].iloc[0]["lag_1"] == pytest.approx(101)
    assert all(float(row.predicted_demand) >= 0 for row in rows)
    assert all(0 <= float(row.lower_bound) <= float(row.predicted_demand) <= float(row.upper_bound) for row in rows)
    assert float(rows[-1].upper_bound - rows[-1].predicted_demand) >= float(rows[0].upper_bound - rows[0].predicted_demand)


def test_confidence_is_clamped_and_declines_with_horizon_error_data_and_age() -> None:
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    fresh = record(mae=10, rows=100, trained_at=datetime(2026, 1, 31, tzinfo=timezone.utc))
    poor = record(mae=30, rows=10, trained_at=datetime(2025, 1, 1, tzinfo=timezone.utc))

    first = ForecastGenerationService.confidence_score(fresh, 100, 1, generated_at=now)
    seventh = ForecastGenerationService.confidence_score(fresh, 100, 7, generated_at=now)
    assert 0 <= seventh <= first <= 100
    assert ForecastGenerationService.confidence_score(poor, 100, 1, generated_at=now) < first


def test_residual_margin_uses_training_metadata_not_an_arbitrary_percentage() -> None:
    assert ForecastGenerationService.residual_margin(record(mae=999)) == pytest.approx(20.0)
