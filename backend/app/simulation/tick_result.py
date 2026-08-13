"""In-memory contract for one completed simulation tick."""

from dataclasses import dataclass, field
from datetime import datetime

from app.simulation.delivery_generator import DeliveryResult
from app.simulation.sales_generator import SaleAdvanceResult
from app.simulation.state import ActiveSaleState, PumpState, TankState


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone.")


@dataclass(frozen=True)
class SimulationTickEvent:
    """An immutable event produced during one simulation tick."""

    event_type: str
    station_id: int
    event_timestamp: datetime
    target_type: str | None = None
    target_id: int | str | None = None
    payload: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type.strip() or self.station_id <= 0:
            raise ValueError("event type and station_id are required.")
        _aware(self.event_timestamp, "event_timestamp")
        if self.target_type is not None and not self.target_type.strip():
            raise ValueError("target_type cannot be empty.")
        object.__setattr__(self, "payload", dict(self.payload))


@dataclass
class SimulationTickResult:
    """Collect all in-memory outcomes of a single station tick."""

    station_id: int
    simulation_time: datetime
    sequence_number: int
    tank_results: list[TankState] = field(default_factory=list)
    pump_results: list[PumpState] = field(default_factory=list)
    sale_results: list[SaleAdvanceResult] = field(default_factory=list)
    completed_sales: list[ActiveSaleState] = field(default_factory=list)
    deliveries: list[DeliveryResult] = field(default_factory=list)
    events: list[SimulationTickEvent] = field(default_factory=list)
    active_scenarios: list[dict[str, object]] = field(default_factory=list)
    created_alarms: list[object] = field(default_factory=list)
    ai_results: list[object] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.station_id <= 0 or self.sequence_number <= 0:
            raise ValueError("station_id and sequence_number must be positive.")
        _aware(self.simulation_time, "simulation_time")

    @property
    def tank_count(self) -> int:
        return len(self.tank_results)

    @property
    def pump_count(self) -> int:
        return len(self.pump_results)

    @property
    def completed_sale_count(self) -> int:
        return len(self.completed_sales)

    @property
    def delivery_count(self) -> int:
        return len(self.deliveries)

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def has_activity(self) -> bool:
        return bool(
            self.sale_results or self.completed_sales or self.deliveries or self.events
        )
