"""Central, testable thresholds and quality penalties for Stage 7 monitoring."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MonitoringRules:
    quality_minimum_score: int = 70
    communication_gap_seconds: int = 300
    sensor_spike_fraction_of_capacity: float = 0.10
    tank_sales_tolerance_liters: float = 2.0
    critical_water_level: float = 5.0
    penalties: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.penalties is None:
            object.__setattr__(
                self,
                "penalties",
                {
                    "MISSING_DATA": 35,
                    "DUPLICATE_READING": 15,
                    "SENSOR_STUCK": 25,
                    "SENSOR_SPIKE": 20,
                    "COMMUNICATION_GAP": 20,
                    "TANK_SALES_MISMATCH": 25,
                    "TIMESTAMP_ERROR": 30,
                    "PHYSICAL_RANGE_VIOLATION": 40,
                    "MISSING_RELATION": 35,
                },
            )


DEFAULT_MONITORING_RULES = MonitoringRules()
