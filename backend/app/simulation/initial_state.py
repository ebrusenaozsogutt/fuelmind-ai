"""Deterministic initial runtime state policies for new simulations."""

from __future__ import annotations

from app.simulation.random_source import RandomSource


# These ranges describe a simulated station's opening inventory.  They are
# intentionally owned by the simulation layer, rather than a UI or a persisted
# observation, so a new run can never inherit a prior run's terminal level.
_FILL_RANGES_BY_FUEL_CODE: dict[str, tuple[float, float]] = {
    "DIESEL": (0.75, 0.80),
    "GASOLINE": (0.65, 0.80),
    "LPG": (0.60, 0.75),
}
_DEFAULT_FILL_RANGE = (0.70, 0.75)


def initial_tank_level_liters(
    *, capacity_liters: float, fuel_code: str, random_seed: int, tank_id: int
) -> float:
    """Return the deterministic opening level for one tank in a new run.

    The tank id is mixed into the run seed so different tanks receive stable,
    independent opening levels without relying on process-global randomness.
    """

    if capacity_liters <= 0:
        raise ValueError("capacity_liters must be greater than zero.")
    lower, upper = _FILL_RANGES_BY_FUEL_CODE.get(
        fuel_code.strip().upper(), _DEFAULT_FILL_RANGE
    )
    source = RandomSource(random_seed + tank_id * 10_007)
    return round(capacity_liters * source.uniform(lower, upper), 3)
