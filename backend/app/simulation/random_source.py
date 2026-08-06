"""Seeded random source for reproducible simulation behavior."""
#seed kullanılan rastgele sayı kaynağı, tekrarlanabilir simülasyon davranışı sağlar.
import random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class RandomSource:
    """Provide deterministic random values without modifying global random state."""

    def __init__(self, seed: int) -> None:
        """Initialize an isolated pseudo-random generator."""

        self._random = random.Random(seed)

    def random(self) -> float:
        """Return the next random value in the half-open interval [0, 1)."""

        return self._random.random()

    def uniform(self, lower: float, upper: float) -> float:
        """Return a uniformly distributed value between two bounds."""

        return self._random.uniform(lower, upper)

    def normal(self, mean: float, standard_deviation: float) -> float:
        """Return a normally distributed value with a non-negative deviation."""

        self._validate_standard_deviation(standard_deviation)
        return self._random.gauss(mean, standard_deviation)

    def randint(self, lower: int, upper: int) -> int:
        """Return a deterministic integer between inclusive bounds."""

        return self._random.randint(lower, upper)

    def choice(self, sequence: Sequence[T]) -> T:
        """Return one deterministic item from a non-empty sequence."""

        if not sequence:
            raise ValueError("choice() cannot select from an empty sequence.")
        return self._random.choice(sequence)

    def chance(self, probability: float) -> bool:
        """Return whether an event occurs for a probability in [0, 1]."""

        if not 0 <= probability <= 1:
            raise ValueError("probability must be between 0 and 1.")
        if probability == 0:
            return False
        if probability == 1:
            return True
        return self.random() < probability

    def clamped_normal(
        self,
        mean: float,
        standard_deviation: float,
        minimum: float,
        maximum: float,
    ) -> float:
        """Return a normal value clamped to inclusive minimum and maximum bounds."""

        if minimum > maximum:
            raise ValueError("minimum cannot be greater than maximum.")
        return min(max(self.normal(mean, standard_deviation), minimum), maximum)

    @staticmethod
    def _validate_standard_deviation(standard_deviation: float) -> None:
        if standard_deviation < 0:
            raise ValueError("standard_deviation cannot be negative.")
