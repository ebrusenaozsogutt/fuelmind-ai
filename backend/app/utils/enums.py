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
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class SimulationTargetType(str, Enum):
    STATION = "STATION"
    TANK = "TANK"
    PUMP = "PUMP"
