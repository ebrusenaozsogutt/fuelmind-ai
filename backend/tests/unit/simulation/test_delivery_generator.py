"""Unit tests for simulated delivery generation."""

from datetime import datetime, timezone

import pytest

from app.simulation import DeliveryGenerator, RandomSource, StationSimulationState, TankState
from app.simulation.enums import SourceType

TIME = datetime(2026, 8, 6, 11, tzinfo=timezone.utc)


def _tank(level: float = 500.0, active: bool = True) -> TankState:
    return TankState(1, 1, 1, "T-1", 1_000.0, level, 500.0, 200.0, 100.0, 20.0, 0.0, "OK", active)


def _generator(seed: int = 42) -> DeliveryGenerator:
    return DeliveryGenerator(random_source=RandomSource(seed))


def test_manual_delivery_updates_true_level_only() -> None:
    tank = _tank()
    result = _generator().create_manual_delivery(tank=tank, quantity_liters=200, delivery_timestamp=TIME, supplier_name=" Demo ")
    assert (result.level_before_liters, result.level_after_liters, result.delivered_quantity_liters) == (500.0, 700.0, 200.0)
    assert tank.measured_level_liters == 500.0
    assert result.supplier_name == "Demo" and not result.is_automatic and result.source_type == SourceType.SIMULATION


def test_manual_delivery_clamps_at_capacity() -> None:
    result = _generator().create_manual_delivery(tank=_tank(900), quantity_liters=200, delivery_timestamp=TIME)
    assert result.delivered_quantity_liters == 100 and result.was_clamped


@pytest.mark.parametrize("quantity", [0, -1, float("nan"), float("inf"), True])
def test_manual_delivery_rejects_invalid_quantity_without_mutation(quantity: float) -> None:
    tank = _tank()
    with pytest.raises(ValueError):
        _generator().create_manual_delivery(tank=tank, quantity_liters=quantity, delivery_timestamp=TIME)
    assert tank.true_level_liters == 500.0


def test_manual_rejects_full_inactive_and_naive_tanks() -> None:
    for tank in (_tank(1_000), _tank(active=False)):
        with pytest.raises(ValueError):
            _generator().create_manual_delivery(tank=tank, quantity_liters=1, delivery_timestamp=TIME)
    with pytest.raises(ValueError):
        _generator().create_manual_delivery(tank=_tank(), quantity_liters=1, delivery_timestamp=TIME.replace(tzinfo=None))


def test_automatic_decision_respects_stock_and_probability() -> None:
    generator = _generator()
    assert not generator.should_create_automatic_delivery(tank=_tank(300), probability=1)
    assert not generator.should_create_automatic_delivery(tank=_tank(200), probability=0)
    assert generator.should_create_automatic_delivery(tank=_tank(200), probability=1)


@pytest.mark.parametrize("probability", [-1, 2, float("nan"), True])
def test_automatic_rejects_invalid_probability(probability: float) -> None:
    with pytest.raises(ValueError):
        _generator().should_create_automatic_delivery(tank=_tank(200), probability=probability)


def test_automatic_delivery_is_deterministic_bounded_and_preserves_measurement() -> None:
    first, second = _tank(100), _tank(100)
    result = _generator(7).create_automatic_delivery(tank=first, delivery_timestamp=TIME)
    duplicate = _generator(7).create_automatic_delivery(tank=second, delivery_timestamp=TIME)
    assert result is not None and duplicate is not None
    assert result.delivered_quantity_liters == duplicate.delivered_quantity_liters
    assert 750 <= first.true_level_liters <= 900 and first.measured_level_liters == 500.0
    assert result.is_automatic and result.delivery_id == duplicate.delivery_id


def test_automatic_deliveries_are_sorted_and_skip_ineligible() -> None:
    state = StationSimulationState(1)
    first, second = _tank(100), _tank(300)
    second.tank_id = 2
    state.add_tank(second)
    state.add_tank(first)
    results = _generator().create_automatic_deliveries(station_state=state, delivery_timestamp=TIME)
    assert [item.tank_id for item in results] == [1]
