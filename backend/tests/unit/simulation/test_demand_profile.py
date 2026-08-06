"""Demand profile tests."""

from datetime import datetime, timedelta, timezone

import pytest

from app.simulation.demand_profile import DemandProfile

ISTANBUL = timezone(timedelta(hours=3))


def moment(hour: int, minute: int = 0, weekday_date: int = 3) -> datetime:
    """Return an aware August 2026 moment for deterministic demand tests."""

    return datetime(2026, 8, weekday_date, hour, minute, tzinfo=ISTANBUL)


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (0, 0, 0.45),
        (5, 59, 0.45),
        (6, 0, 1.35),
        (8, 59, 1.35),
        (9, 0, 1.00),
        (12, 0, 1.15),
        (14, 0, 0.95),
        (17, 0, 1.40),
        (21, 0, 0.70),
        (23, 59, 0.70),
    ],
)
def test_hour_multiplier_boundaries(hour: int, minute: int, expected: float) -> None:
    assert DemandProfile().get_hour_multiplier(moment(hour, minute)) == expected


@pytest.mark.parametrize(
    ("date", "hour", "expected"),
    [
        (3, 10, 1.00),
        (7, 10, 1.12),
        (8, 10, 1.18),
        (9, 11, 0.75),
        (9, 12, 0.90),
        (9, 17, 1.10),
    ],
)
def test_day_multiplier_boundaries(date: int, hour: int, expected: float) -> None:
    assert DemandProfile().get_day_multiplier(moment(hour, weekday_date=date)) == expected


@pytest.mark.parametrize(
    ("fuel_code", "expected"),
    [
        ("DIESEL", 1.20),
        (" motorin ", 1.20),
        ("MOTORİN", 1.20),
        ("GASOLINE", 1.00),
        ("benzin", 1.00),
        ("BENZİN", 1.00),
        ("LPG", 0.82),
    ],
)
def test_fuel_multipliers_and_aliases(fuel_code: str, expected: float) -> None:
    assert DemandProfile().get_fuel_multiplier(fuel_code) == expected


@pytest.mark.parametrize("fuel_code", ["", "UNKNOWN"])
def test_invalid_fuel_code_is_rejected(fuel_code: str) -> None:
    with pytest.raises(ValueError):
        DemandProfile().get_fuel_multiplier(fuel_code)


def test_combined_multiplier_matches_friday_morning_diesel_example() -> None:
    friday_at_seven = moment(7, weekday_date=7)

    assert DemandProfile().get_combined_multiplier(friday_at_seven, "DIESEL") == pytest.approx(1.8144)


def test_probability_applies_scenario_multiplier_and_clamps() -> None:
    profile = DemandProfile()
    value = profile.calculate_sale_probability(0.08, moment(7, weekday_date=7), "DIESEL", 0.5)

    assert value == pytest.approx(0.072576)
    assert profile.calculate_sale_probability(1, moment(17, weekday_date=8), "DIESEL", 2) == 1
    assert profile.calculate_sale_probability(0, moment(7), "LPG") == 0


@pytest.mark.parametrize("base_probability", [-0.1, 1.1])
def test_invalid_base_probability_is_rejected(base_probability: float) -> None:
    with pytest.raises(ValueError):
        DemandProfile().calculate_sale_probability(base_probability, moment(7), "LPG")


@pytest.mark.parametrize("scenario_multiplier", [0, -1])
def test_invalid_scenario_multiplier_is_rejected(scenario_multiplier: float) -> None:
    with pytest.raises(ValueError):
        DemandProfile().calculate_sale_probability(0.1, moment(7), "LPG", scenario_multiplier)


def test_naive_datetime_is_rejected_and_calculations_are_deterministic() -> None:
    profile = DemandProfile()
    with pytest.raises(ValueError):
        profile.get_hour_multiplier(datetime(2026, 8, 3, 7))

    first = profile.calculate_sale_probability(0.08, moment(7), "DIESEL")
    second = profile.calculate_sale_probability(0.08, moment(7), "DIESEL")
    assert first == second
