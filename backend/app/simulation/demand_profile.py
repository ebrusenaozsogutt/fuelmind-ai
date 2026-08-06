"""Deterministic demand multipliers for simulation sale-start decisions."""

from datetime import datetime
from math import isfinite
from numbers import Real
from types import MappingProxyType


class DemandProfile:
    """Calculate time, day, and fuel demand multipliers without side effects."""

    _FUEL_ALIASES = MappingProxyType(
        {
            "DIESEL": "DIESEL",
            "MOTORIN": "DIESEL",
            "MOTORİN": "DIESEL",
            "GASOLINE": "GASOLINE",
            "BENZIN": "GASOLINE",
            "BENZİN": "GASOLINE",
            "LPG": "LPG",
        }
    )
    _FUEL_MULTIPLIERS = MappingProxyType(
        {"DIESEL": 1.20, "GASOLINE": 1.00, "LPG": 0.82}
    )

    def get_hour_multiplier(self, moment: datetime) -> float:
        """Return the demand multiplier for the local hour of an aware moment."""

        hour = self._require_aware(moment).hour
        if hour < 6:
            return 0.45
        if hour < 9:
            return 1.35
        if hour < 12:
            return 1.00
        if hour < 14:
            return 1.15
        if hour < 17:
            return 0.95
        if hour < 21:
            return 1.40
        return 0.70

    def get_day_multiplier(self, moment: datetime) -> float:
        """Return the weekday and Sunday time-of-day demand multiplier."""

        moment = self._require_aware(moment)
        weekday = moment.weekday()
        if weekday <= 3:
            return 1.00
        if weekday == 4:
            return 1.12
        if weekday == 5:
            return 1.18
        if moment.hour < 12:
            return 0.75
        if moment.hour >= 17:
            return 1.10
        return 0.90

    def get_fuel_multiplier(self, fuel_code: str) -> float:
        """Return the multiplier for an explicitly supported fuel code or alias."""

        canonical_code = self._canonical_fuel_code(fuel_code)
        return self._FUEL_MULTIPLIERS[canonical_code]

    def get_combined_multiplier(self, moment: datetime, fuel_code: str) -> float:
        """Return hour × day × fuel demand multiplier for an aware moment."""

        combined = (
            self.get_hour_multiplier(moment)
            * self.get_day_multiplier(moment)
            * self.get_fuel_multiplier(fuel_code)
        )
        if combined <= 0:
            raise ValueError("Combined demand multiplier must be greater than zero.")
        return combined

    def calculate_sale_probability(
        self,
        base_probability: float,
        moment: datetime,
        fuel_code: str,
        scenario_multiplier: float = 1.0,
    ) -> float:
        """Calculate a clamped sale-start probability without using randomness."""

        base_probability = self._probability(base_probability, "base_probability")
        scenario_multiplier = self._positive_number(
            scenario_multiplier, "scenario_multiplier"
        )
        probability = (
            base_probability
            * self.get_combined_multiplier(moment, fuel_code)
            * scenario_multiplier
        )
        return min(probability, 1.0)

    @staticmethod
    def _require_aware(moment: datetime) -> datetime:
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("moment must include a timezone.")
        return moment

    def _canonical_fuel_code(self, fuel_code: str) -> str:
        if not isinstance(fuel_code, str):
            raise ValueError("fuel_code must be a non-empty string.")
        normalized = fuel_code.strip().upper()
        if not normalized:
            raise ValueError("fuel_code cannot be empty.")
        try:
            return self._FUEL_ALIASES[normalized]
        except KeyError as exc:
            raise ValueError(f"Unsupported fuel code: {fuel_code!r}.") from exc

    @staticmethod
    def _positive_number(value: Real, field_name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
            raise ValueError(f"{field_name} must be a finite numeric value.")
        if value <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return float(value)

    @staticmethod
    def _probability(value: Real, field_name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
            raise ValueError(f"{field_name} must be a finite numeric value.")
        if not 0 <= value <= 1:
            raise ValueError(f"{field_name} must be between 0 and 1.")
        return float(value)
