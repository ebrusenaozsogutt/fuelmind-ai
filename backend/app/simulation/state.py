"""In-memory state models used by simulation runtime components."""

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from numbers import Real

from app.utils.enums import PumpStatus

_EPSILON = 1e-9


def _positive_id(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")
    return value


def _non_negative_float(value: Real, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f"{field_name} must be a finite numeric value.")
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return float(value)


def _finite_float(value: Real, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f"{field_name} must be a finite numeric value.")
    return float(value)


def _positive_float(value: Real, field_name: str) -> float:
    value = _non_negative_float(value, field_name)
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return value


def _aware_time(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone.")
    return value


def _required_code(value: str, field_name: str = "code") -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty.")
    return value


@dataclass
class TankState:
    """Physical and measured tank state held only in simulation memory."""

    tank_id: int
    station_id: int
    fuel_type_id: int
    code: str
    capacity_liters: float
    true_level_liters: float
    measured_level_liters: float
    minimum_safe_level: float
    critical_level: float
    temperature: float
    water_level: float
    sensor_status: str
    is_active: bool = True

    def __post_init__(self) -> None:
        self.tank_id = _positive_id(self.tank_id, "tank_id")
        self.station_id = _positive_id(self.station_id, "station_id")
        self.fuel_type_id = _positive_id(self.fuel_type_id, "fuel_type_id")
        self.code = _required_code(self.code)
        self.capacity_liters = _positive_float(self.capacity_liters, "capacity_liters")
        self.true_level_liters = _non_negative_float(
            self.true_level_liters, "true_level_liters"
        )
        self.measured_level_liters = _non_negative_float(
            self.measured_level_liters, "measured_level_liters"
        )
        self.minimum_safe_level = _non_negative_float(
            self.minimum_safe_level, "minimum_safe_level"
        )
        self.critical_level = _non_negative_float(self.critical_level, "critical_level")
        self.temperature = _finite_float(self.temperature, "temperature")
        self.water_level = _non_negative_float(self.water_level, "water_level")
        if not self.sensor_status.strip():
            raise ValueError("sensor_status cannot be empty.")
        self.sensor_status = self.sensor_status.strip()
        for field_name in (
            "true_level_liters",
            "measured_level_liters",
            "minimum_safe_level",
            "critical_level",
        ):
            if getattr(self, field_name) > self.capacity_liters + _EPSILON:
                raise ValueError(f"{field_name} cannot exceed capacity_liters.")

    @property
    def available_liters(self) -> float:
        """Return the current physical fuel level."""

        return self.true_level_liters

    @property
    def fill_percentage(self) -> float:
        """Return the physical fill percentage of the tank."""

        return self.true_level_liters / self.capacity_liters * 100

    def can_withdraw(self, quantity_liters: float) -> bool:
        """Return whether a positive quantity can be withdrawn safely."""

        try:
            quantity = _positive_float(quantity_liters, "quantity_liters")
        except ValueError:
            return False
        return quantity <= self.true_level_liters + _EPSILON

    def withdraw(self, quantity_liters: float) -> None:
        """Subtract a positive quantity from the physical level."""

        quantity = _positive_float(quantity_liters, "quantity_liters")
        if not self.can_withdraw(quantity):
            raise ValueError("Tank does not contain enough fuel.")
        remaining = self.true_level_liters - quantity
        self.true_level_liters = 0.0 if remaining < _EPSILON else remaining

    def can_receive(self, quantity_liters: float) -> bool:
        """Return whether a positive quantity fits without exceeding capacity."""

        try:
            quantity = _positive_float(quantity_liters, "quantity_liters")
        except ValueError:
            return False
        return self.true_level_liters + quantity <= self.capacity_liters + _EPSILON

    def receive(self, quantity_liters: float) -> None:
        """Add a positive quantity to the physical level."""

        quantity = _positive_float(quantity_liters, "quantity_liters")
        if not self.can_receive(quantity):
            raise ValueError("Tank capacity would be exceeded.")
        level = self.true_level_liters + quantity
        self.true_level_liters = (
            self.capacity_liters
            if abs(level - self.capacity_liters) < _EPSILON
            else level
        )

    def update_measured_level(self, value: float) -> None:
        """Set a valid measured level without changing the physical level."""

        value = _non_negative_float(value, "measured_level_liters")
        if value > self.capacity_liters + _EPSILON:
            raise ValueError("measured_level_liters cannot exceed capacity_liters.")
        self.measured_level_liters = min(value, self.capacity_liters)


@dataclass
class PumpState:
    """Live pump status and sensor state held in simulation memory."""

    pump_id: int
    station_id: int
    tank_id: int
    fuel_type_id: int
    code: str
    status: PumpStatus
    nominal_flow_rate: float
    minimum_flow_rate: float
    maximum_motor_current: float
    maximum_pressure: float
    flow_rate: float = 0.0
    pressure: float = 0.0
    motor_current: float = 0.0
    temperature: float = 0.0
    total_working_hours: float = 0.0
    error_count: int = 0
    is_active: bool = True

    def __post_init__(self) -> None:
        self.pump_id = _positive_id(self.pump_id, "pump_id")
        self.station_id = _positive_id(self.station_id, "station_id")
        self.tank_id = _positive_id(self.tank_id, "tank_id")
        self.fuel_type_id = _positive_id(self.fuel_type_id, "fuel_type_id")
        self.code = _required_code(self.code)
        self.status = PumpStatus(self.status)
        for field_name in (
            "nominal_flow_rate",
            "minimum_flow_rate",
            "maximum_motor_current",
            "maximum_pressure",
            "flow_rate",
            "pressure",
            "motor_current",
            "temperature",
            "total_working_hours",
        ):
            setattr(self, field_name, _non_negative_float(getattr(self, field_name), field_name))
        if self.minimum_flow_rate > self.nominal_flow_rate:
            raise ValueError("minimum_flow_rate cannot exceed nominal_flow_rate.")
        if isinstance(self.error_count, bool) or self.error_count < 0:
            raise ValueError("error_count cannot be negative.")

    @property
    def is_idle(self) -> bool:
        """Return whether the pump is idle."""

        return self.status == PumpStatus.IDLE

    @property
    def is_active_status(self) -> bool:
        """Return whether the pump is actively dispensing."""

        return self.is_active and self.status == PumpStatus.ACTIVE

    def start_dispensing(self) -> None:
        """Move an enabled idle pump into its ACTIVE dispensing status."""

        if not self.is_active:
            raise ValueError("Inactive pump cannot start dispensing.")
        if self.status == PumpStatus.IDLE:
            self.status = PumpStatus.ACTIVE
            return
        if self.status != PumpStatus.ACTIVE:
            raise ValueError(f"Pump cannot dispense while {self.status.value}.")

    def stop_dispensing(self) -> None:
        """Move the pump to IDLE and reset flow-related sensor values."""

        self.status = PumpStatus.IDLE
        self.flow_rate = 0.0
        self.pressure = 0.0
        self.motor_current = 0.0

    def set_sensor_values(
        self,
        *,
        flow_rate: float,
        pressure: float,
        motor_current: float,
        temperature: float,
    ) -> None:
        """Set non-negative live sensor values."""

        self.flow_rate = _non_negative_float(flow_rate, "flow_rate")
        self.pressure = _non_negative_float(pressure, "pressure")
        self.motor_current = _non_negative_float(motor_current, "motor_current")
        self.temperature = _non_negative_float(temperature, "temperature")

    def increment_working_time(self, seconds: float) -> None:
        """Add a non-negative elapsed duration, expressed in seconds."""

        self.total_working_hours += _non_negative_float(seconds, "seconds") / 3600

    def increment_error_count(self) -> None:
        """Record one additional pump error."""

        self.error_count += 1


@dataclass
class ActiveSaleState:
    """In-memory progress state for a sale that has not yet completed."""

    sale_id: str
    station_id: int
    tank_id: int
    pump_id: int
    fuel_type_id: int
    started_at: datetime
    target_quantity_liters: float
    dispensed_quantity_liters: float
    unit_price: float
    last_updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.sale_id = _required_code(self.sale_id, "sale_id")
        self.station_id = _positive_id(self.station_id, "station_id")
        self.tank_id = _positive_id(self.tank_id, "tank_id")
        self.pump_id = _positive_id(self.pump_id, "pump_id")
        self.fuel_type_id = _positive_id(self.fuel_type_id, "fuel_type_id")
        self.started_at = _aware_time(self.started_at, "started_at")
        self.target_quantity_liters = _positive_float(
            self.target_quantity_liters, "target_quantity_liters"
        )
        self.dispensed_quantity_liters = _non_negative_float(
            self.dispensed_quantity_liters, "dispensed_quantity_liters"
        )
        self.unit_price = _non_negative_float(self.unit_price, "unit_price")
        if self.dispensed_quantity_liters > self.target_quantity_liters + _EPSILON:
            raise ValueError("dispensed_quantity_liters cannot exceed target quantity.")
        self.last_updated_at = _aware_time(
            self.last_updated_at or self.started_at, "last_updated_at"
        )
        if self.last_updated_at < self.started_at:
            raise ValueError("last_updated_at cannot precede started_at.")

    @property
    def remaining_quantity_liters(self) -> float:
        """Return the quantity that remains to be dispensed."""

        return max(0.0, self.target_quantity_liters - self.dispensed_quantity_liters)

    @property
    def progress_percentage(self) -> float:
        """Return completion progress in the inclusive range 0 to 100."""

        return min(100.0, self.dispensed_quantity_liters / self.target_quantity_liters * 100)

    @property
    def is_completed(self) -> bool:
        """Return whether the requested quantity has been fully dispensed."""

        return self.remaining_quantity_liters < _EPSILON

    def dispense(self, quantity_liters: float, updated_at: datetime) -> float:
        """Dispense up to the remaining quantity and return the actual amount."""

        quantity = _positive_float(quantity_liters, "quantity_liters")
        updated_at = _aware_time(updated_at, "updated_at")
        if updated_at < self.started_at or updated_at < self.last_updated_at:
            raise ValueError("updated_at cannot precede the active sale timeline.")
        if self.is_completed:
            raise ValueError("Completed sale cannot dispense more fuel.")
        dispensed = min(quantity, self.remaining_quantity_liters)
        self.dispensed_quantity_liters += dispensed
        self.last_updated_at = updated_at
        return dispensed


@dataclass
class StationSimulationState:
    """Aggregate in-memory state for one station simulation."""

    station_id: int
    tanks: dict[int, TankState] = field(default_factory=dict)
    pumps: dict[int, PumpState] = field(default_factory=dict)
    active_sales: dict[int, ActiveSaleState] = field(default_factory=dict)
    sequence_number: int = 0

    def __post_init__(self) -> None:
        self.station_id = _positive_id(self.station_id, "station_id")
        if self.sequence_number < 0:
            raise ValueError("sequence_number cannot be negative.")

    def add_tank(self, tank: TankState) -> None:
        """Add a station-owned tank state exactly once."""

        if tank.station_id != self.station_id:
            raise ValueError("Tank belongs to a different station.")
        if tank.tank_id in self.tanks:
            raise ValueError("Tank is already registered in this station state.")
        self.tanks[tank.tank_id] = tank

    def add_pump(self, pump: PumpState) -> None:
        """Add a pump whose tank and fuel type match this station state."""

        if pump.station_id != self.station_id:
            raise ValueError("Pump belongs to a different station.")
        if pump.pump_id in self.pumps:
            raise ValueError("Pump is already registered in this station state.")
        tank = self.get_tank(pump.tank_id)
        if pump.fuel_type_id != tank.fuel_type_id:
            raise ValueError("Pump fuel type must match its tank fuel type.")
        self.pumps[pump.pump_id] = pump

    def get_tank(self, tank_id: int) -> TankState:
        """Return a registered tank or raise a clear KeyError."""

        try:
            return self.tanks[tank_id]
        except KeyError as exc:
            raise KeyError(f"Tank {tank_id} is not registered.") from exc

    def get_pump(self, pump_id: int) -> PumpState:
        """Return a registered pump or raise a clear KeyError."""

        try:
            return self.pumps[pump_id]
        except KeyError as exc:
            raise KeyError(f"Pump {pump_id} is not registered.") from exc

    def start_sale(self, sale: ActiveSaleState) -> None:
        """Register one relationship-compatible active sale for a pump."""

        pump = self.get_pump(sale.pump_id)
        tank = self.get_tank(sale.tank_id)
        if sale.pump_id in self.active_sales:
            raise ValueError("Pump already has an active sale.")
        if (
            sale.station_id != self.station_id
            or pump.tank_id != tank.tank_id
            or sale.tank_id != pump.tank_id
            or sale.fuel_type_id != tank.fuel_type_id
            or sale.fuel_type_id != pump.fuel_type_id
        ):
            raise ValueError("Active sale relationships are incompatible.")
        self.active_sales[sale.pump_id] = sale

    def get_active_sale(self, pump_id: int) -> ActiveSaleState:
        """Return the active sale for a pump or raise a clear KeyError."""

        try:
            return self.active_sales[pump_id]
        except KeyError as exc:
            raise KeyError(f"Pump {pump_id} has no active sale.") from exc

    def complete_sale(self, pump_id: int) -> ActiveSaleState:
        """Remove and return a pump's active sale."""

        return self.active_sales.pop(pump_id)

    def has_active_sale(self, pump_id: int) -> bool:
        """Return whether a pump already has an active sale."""

        return pump_id in self.active_sales

    def next_sequence(self) -> int:
        """Increment and return the station state sequence number."""

        self.sequence_number += 1
        return self.sequence_number
