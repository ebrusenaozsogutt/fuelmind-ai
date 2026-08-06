"""Seeded random source tests."""

import pytest

from app.simulation.random_source import RandomSource


def test_same_seed_produces_same_sequence() -> None:
    first = RandomSource(42)
    second = RandomSource(42)

    assert [first.random() for _ in range(4)] == [second.random() for _ in range(4)]


def test_different_seeds_produce_different_sequences() -> None:
    first = RandomSource(42)
    second = RandomSource(43)

    assert [first.random() for _ in range(4)] != [second.random() for _ in range(4)]


def test_chance_boundary_values_are_deterministic() -> None:
    source = RandomSource(42)

    assert not source.chance(0)
    assert source.chance(1)


@pytest.mark.parametrize("probability", [-0.1, 1.1])
def test_invalid_probability_is_rejected(probability: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        RandomSource(42).chance(probability)


def test_clamped_normal_stays_within_bounds() -> None:
    value = RandomSource(42).clamped_normal(100, 10, 95, 105)

    assert 95 <= value <= 105


def test_negative_standard_deviation_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        RandomSource(42).normal(0, -1)


def test_choice_rejects_an_empty_sequence() -> None:
    with pytest.raises(ValueError, match="empty sequence"):
        RandomSource(42).choice([])


def test_uniform_randint_and_choice_are_deterministic() -> None:
    first = RandomSource(42)
    second = RandomSource(42)

    assert first.uniform(1, 2) == second.uniform(1, 2)
    assert first.randint(1, 10) == second.randint(1, 10)
    assert first.choice(["a", "b", "c"]) == second.choice(["a", "b", "c"])
