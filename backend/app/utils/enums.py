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


class AlarmStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


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


class ScenarioType(str, Enum):
    """Supported, deliberately bounded demo scenarios."""

    FLOW_DROP = "FLOW_DROP"
    HIGH_MOTOR_CURRENT = "HIGH_MOTOR_CURRENT"
    TANK_LEAK = "TANK_LEAK"
    SENSOR_STUCK = "SENSOR_STUCK"
    SENSOR_SPIKE = "SENSOR_SPIKE"
    WATER_LEVEL_RISE = "WATER_LEVEL_RISE"
    DEMAND_SURGE = "DEMAND_SURGE"


class SourceType(str, Enum):
    """Origin of persisted sensor data."""

    SIMULATION = "SIMULATION"
    CSV_IMPORT = "CSV_IMPORT"
    REAL_DEVICE = "REAL_DEVICE"
    MANUAL = "MANUAL"
