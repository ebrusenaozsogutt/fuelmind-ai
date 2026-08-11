"""Rule-based data-quality scoring for sensor observations."""

from dataclasses import dataclass
from decimal import Decimal
from app.services.monitoring_rules import DEFAULT_MONITORING_RULES, MonitoringRules


@dataclass(frozen=True)
class QualityAssessment:
    score: Decimal
    flags: list[str]


class DataQualityService:
    def __init__(self, rules: MonitoringRules = DEFAULT_MONITORING_RULES) -> None:
        self.rules = rules

    def assess(
        self,
        reading: object,
        *,
        previous: object | None = None,
        capacity_liters: float | None = None,
        expected_sale_change: float = 0.0,
    ) -> QualityAssessment:
        flags: set[str] = set()
        names = (
            "tank_level",
            "true_tank_level",
            "flow_rate",
            "pressure",
            "motor_current",
            "water_level",
        )
        if all(getattr(reading, name, None) is None for name in names):
            flags.add("MISSING_DATA")
        if (
            getattr(reading, "tank_id", None) is None
            and getattr(reading, "pump_id", None) is None
        ):
            flags.add("MISSING_RELATION")
        level = self._float(getattr(reading, "tank_level", None))
        if level is not None and (
            level < 0 or capacity_liters is not None and level > capacity_liters
        ):
            flags.add("PHYSICAL_RANGE_VIOLATION")
        if previous is not None:
            current_time, prior_time = (
                reading.reading_timestamp,
                previous.reading_timestamp,
            )
            # SQLite test fixtures may return naive timestamps while production
            # PostgreSQL preserves UTC offsets; compare the same instant basis.
            if current_time.tzinfo is not None and prior_time.tzinfo is None:
                prior_time = prior_time.replace(tzinfo=current_time.tzinfo)
            if current_time <= prior_time:
                flags.add("TIMESTAMP_ERROR")
            elif (
                current_time - prior_time
            ).total_seconds() > self.rules.communication_gap_seconds:
                flags.add("COMMUNICATION_GAP")
            if all(
                getattr(reading, name, None) == getattr(previous, name, None)
                for name in names
            ):
                flags.add("DUPLICATE_READING")
            previous_level = self._float(getattr(previous, "tank_level", None))
            if level is not None and previous_level is not None:
                delta = level - previous_level
                if abs(delta) < 1e-6 and expected_sale_change > 0:
                    flags.add("SENSOR_STUCK")
                if (
                    capacity_liters
                    and abs(delta)
                    > capacity_liters * self.rules.sensor_spike_fraction_of_capacity
                ):
                    flags.add("SENSOR_SPIKE")
                true_level, prior_true = (
                    self._float(getattr(reading, "true_tank_level", None)),
                    self._float(getattr(previous, "true_tank_level", None)),
                )
                if (
                    true_level is not None
                    and prior_true is not None
                    and prior_true - true_level - expected_sale_change
                    > self.rules.tank_sales_tolerance_liters
                ):
                    flags.add("TANK_SALES_MISMATCH")
        penalty = sum(self.rules.penalties[flag] for flag in flags)  # type: ignore[index]
        return QualityAssessment(Decimal(str(max(0, 100 - penalty))), sorted(flags))

    @staticmethod
    def _float(value: object) -> float | None:
        return None if value is None else float(value)
