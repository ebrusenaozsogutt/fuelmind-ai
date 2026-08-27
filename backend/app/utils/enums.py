"""Shared string enums stored as uppercase text values in the database."""

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"


class PumpStatus(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    MAINTENANCE = "MAINTENANCE"
    FAULT = "FAULT"
    OFFLINE = "OFFLINE"


class ControllerType(str, Enum):
    """Supported forecourt controller categories."""

    USC = "USC"
    GENERIC = "GENERIC"


class ControllerStatus(str, Enum):
    """Connectivity state reported for a forecourt controller."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"
    STARTING = "STARTING"


class PortType(str, Enum):
    """Logical purpose of a controller communication port."""

    PUMP = "PUMP"
    PROBE = "PROBE"
    GENERIC = "GENERIC"


class PortStatus(str, Enum):
    """Connectivity state reported for a communication port."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class ProbeStatus(str, Enum):
    """Availability state reported for a tank probe."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    FAULT = "FAULT"
    UNKNOWN = "UNKNOWN"


class NozzleStatus(str, Enum):
    """Operational state of a pump nozzle."""

    AVAILABLE = "AVAILABLE"
    DISPENSING = "DISPENSING"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    FAULT = "FAULT"


class AlarmStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class FaultStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"


class FaultType(str, Enum):
    COMMUNICATION = "COMMUNICATION"
    CONNECTION = "CONNECTION"
    INITIALIZATION = "INITIALIZATION"
    INTERFACE = "INTERFACE"
    SENSOR = "SENSOR"
    EQUIPMENT = "EQUIPMENT"
    NOZZLE = "NOZZLE"


class FaultCode(str, Enum):
    INTERFACE_ERROR = "INTERFACE_ERROR"
    PUMP_NOT_CONNECTED = "PUMP_NOT_CONNECTED"
    USC_INITIALIZATION_ERROR = "USC_INITIALIZATION_ERROR"
    PORT_COMMUNICATION_ERROR = "PORT_COMMUNICATION_ERROR"
    PROBE_COMMUNICATION_ERROR = "PROBE_COMMUNICATION_ERROR"
    SENSOR_ERROR = "SENSOR_ERROR"
    NOZZLE_ERROR = "NOZZLE_ERROR"


class FaultTargetType(str, Enum):
    CONTROLLER = "CONTROLLER"
    PORT = "PORT"
    PUMP = "PUMP"
    PROBE = "PROBE"
    NOZZLE = "NOZZLE"
    TANK = "TANK"
    SENSOR = "SENSOR"


class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    STATUS_CHANGE = "STATUS_CHANGE"
    INVESTIGATE = "INVESTIGATE"
    RESOLVE = "RESOLVE"


class AnomalyType(str, Enum):
    SENSOR_ANOMALY = "SENSOR_ANOMALY"
    EQUIPMENT_ANOMALY = "EQUIPMENT_ANOMALY"
    TRANSACTION_ANOMALY = "TRANSACTION_ANOMALY"
    DEMAND_ANOMALY = "DEMAND_ANOMALY"
    DATA_QUALITY_ANOMALY = "DATA_QUALITY_ANOMALY"


class AlarmSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SensorStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WARNING = "WARNING"
    FAULT = "FAULT"
    OFFLINE = "OFFLINE"


class RecommendationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationStatus(str, Enum):
    NEW = "NEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class SimulationStatus(str, Enum):
    CREATED = "CREATED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class SimulationMode(str, Enum):
    """Persisted execution mode for a simulation run."""

    REALTIME = "REALTIME"
    ACCELERATED = "ACCELERATED"
    DATASET = "DATASET"


class SimulationTargetType(str, Enum):
    STATION = "STATION"
    TANK = "TANK"
    PUMP = "PUMP"
    CONTROLLER = "CONTROLLER"
    PORT = "PORT"
    PROBE = "PROBE"


class ScenarioType(str, Enum):
    """Supported, deliberately bounded demo scenarios."""

    FLOW_DROP = "FLOW_DROP"
    HIGH_MOTOR_CURRENT = "HIGH_MOTOR_CURRENT"
    TANK_LEAK = "TANK_LEAK"
    SENSOR_STUCK = "SENSOR_STUCK"
    SENSOR_SPIKE = "SENSOR_SPIKE"
    WATER_LEVEL_RISE = "WATER_LEVEL_RISE"
    DEMAND_SURGE = "DEMAND_SURGE"
    PORT_COMMUNICATION_ERROR = "PORT_COMMUNICATION_ERROR"
    USC_INITIALIZATION_ERROR = "USC_INITIALIZATION_ERROR"
    PROBE_COMMUNICATION_ERROR = "PROBE_COMMUNICATION_ERROR"
    PUMP_NOT_CONNECTED = "PUMP_NOT_CONNECTED"


class SourceType(str, Enum):
    """Origin of persisted sensor data."""

    SIMULATION = "SIMULATION"
    CSV_IMPORT = "CSV_IMPORT"
    REAL_DEVICE = "REAL_DEVICE"
    MANUAL = "MANUAL"


class CustomerType(str, Enum):
    """Commercial customer classification."""

    COMPANY = "COMPANY"
    INDIVIDUAL = "INDIVIDUAL"


class CustomerRequestStatus(str, Enum):
    """Lifecycle state for customer and fleet definition requests."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class CardStatus(str, Enum):
    """Operational state of a fuel card."""

    ACTIVE = "ACTIVE"
    PASSIVE = "PASSIVE"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"


class CardLimitType(str, Enum):
    """Supported periods for fuel-card quantity limits."""

    PER_TRANSACTION = "PER_TRANSACTION"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CUSTOM = "CUSTOM"


class PaymentType(str, Enum):
    """Commercial settlement type for a fuel card."""

    PREPAID = "PREPAID"
    CREDIT = "CREDIT"


class SaleStatus(str, Enum):
    """Commercial fuel-sale lifecycle state."""

    AUTHORIZED = "AUTHORIZED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class DriverAssignmentStatus(str, Enum):
    """Lifecycle state of a driver-to-vehicle assignment."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CardAuthorizationDecision(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    CARD_NOT_FOUND = "CARD_NOT_FOUND"
    CARD_INACTIVE = "CARD_INACTIVE"
    CARD_PASSIVE = "CARD_PASSIVE"
    CARD_BLOCKED = "CARD_BLOCKED"
    CARD_EXPIRED = "CARD_EXPIRED"
    CARD_NOT_YET_VALID = "CARD_NOT_YET_VALID"
    VEHICLE_NOT_FOUND = "VEHICLE_NOT_FOUND"
    VEHICLE_INACTIVE = "VEHICLE_INACTIVE"
    VEHICLE_MISMATCH = "VEHICLE_MISMATCH"
    VEHICLE_HIERARCHY_INACTIVE = "VEHICLE_HIERARCHY_INACTIVE"
    STATION_NOT_FOUND = "STATION_NOT_FOUND"
    STATION_NOT_ALLOWED = "STATION_NOT_ALLOWED"
    FUEL_TYPE_NOT_FOUND = "FUEL_TYPE_NOT_FOUND"
    FUEL_NOT_ALLOWED = "FUEL_NOT_ALLOWED"
    DAY_NOT_ALLOWED = "DAY_NOT_ALLOWED"
    TIME_NOT_ALLOWED = "TIME_NOT_ALLOWED"
    TRANSACTION_LIMIT_EXCEEDED = "TRANSACTION_LIMIT_EXCEEDED"
    DAILY_LIMIT_EXCEEDED = "DAILY_LIMIT_EXCEEDED"
    WEEKLY_LIMIT_EXCEEDED = "WEEKLY_LIMIT_EXCEEDED"
    MONTHLY_LIMIT_EXCEEDED = "MONTHLY_LIMIT_EXCEEDED"
    CUSTOM_LIMIT_EXCEEDED = "CUSTOM_LIMIT_EXCEEDED"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INSUFFICIENT_PREPAID_BALANCE = "INSUFFICIENT_PREPAID_BALANCE"
    CREDIT_LIMIT_EXCEEDED = "CREDIT_LIMIT_EXCEEDED"
    FUEL_PRICE_NOT_CONFIGURED = "FUEL_PRICE_NOT_CONFIGURED"
