"""Shared enum contract tests."""

from enum import Enum

import pytest
from pydantic import BaseModel, ValidationError

from app.utils.enums import (
    AlarmStatus,
    AnomalyType,
    CardLimitType,
    CardStatus,
    ControllerStatus,
    ControllerType,
    CustomerRequestStatus,
    CustomerType,
    DriverAssignmentStatus,
    NozzleStatus,
    PortStatus,
    PortType,
    PaymentType,
    ProbeStatus,
    PumpStatus,
    SaleStatus,
    UserRole,
)


class EnumPayload(BaseModel):
    """Exercise Pydantic validation and JSON serialization for enum values."""

    value: UserRole | PumpStatus | AlarmStatus | AnomalyType


@pytest.mark.parametrize(
    ("enum_type", "expected_values"),
    [
        (UserRole, {"ADMIN", "OPERATOR"}),
        (PumpStatus, {"ACTIVE", "IDLE", "MAINTENANCE", "FAULT", "OFFLINE"}),
        (ControllerType, {"USC", "GENERIC"}),
        (ControllerStatus, {"ONLINE", "OFFLINE", "ERROR", "STARTING"}),
        (PortType, {"PUMP", "PROBE", "GENERIC"}),
        (PortStatus, {"ONLINE", "OFFLINE", "DEGRADED", "ERROR"}),
        (ProbeStatus, {"ONLINE", "OFFLINE", "FAULT", "UNKNOWN"}),
        (
            NozzleStatus,
            {"AVAILABLE", "DISPENSING", "OUT_OF_SERVICE", "FAULT"},
        ),
        (
            AlarmStatus,
            {"NEW", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"},
        ),
        (
            AnomalyType,
            {
                "SENSOR_ANOMALY",
                "EQUIPMENT_ANOMALY",
                "TRANSACTION_ANOMALY",
                "DEMAND_ANOMALY",
                "DATA_QUALITY_ANOMALY",
            },
        ),
        (CustomerType, {"COMPANY", "INDIVIDUAL"}),
        (
            CustomerRequestStatus,
            {"PENDING", "APPROVED", "REJECTED", "SUSPENDED"},
        ),
        (CardStatus, {"ACTIVE", "PASSIVE", "BLOCKED", "EXPIRED"}),
        (
            CardLimitType,
            {"PER_TRANSACTION", "DAILY", "WEEKLY", "MONTHLY", "CUSTOM"},
        ),
        (PaymentType, {"PREPAID", "CREDIT"}),
        (
            SaleStatus,
            {"AUTHORIZED", "STARTED", "COMPLETED", "CANCELLED", "FAILED"},
        ),
        (DriverAssignmentStatus, {"ACTIVE", "COMPLETED", "CANCELLED"}),
    ],
)
def test_enum_values_match_database_strings(
    enum_type: type[Enum], expected_values: set[str]
) -> None:
    assert {member.value for member in enum_type} == expected_values


@pytest.mark.parametrize("invalid_value", ["UNKNOWN", "", "active"])
def test_invalid_enum_values_are_rejected(invalid_value: str) -> None:
    with pytest.raises(ValidationError):
        EnumPayload(value=invalid_value)


@pytest.mark.parametrize(
    "value",
    [
        UserRole.ADMIN,
        PumpStatus.MAINTENANCE,
        AlarmStatus.FALSE_POSITIVE,
        AnomalyType.DATA_QUALITY_ANOMALY,
    ],
)
def test_enums_serialize_to_strings_in_pydantic(value: Enum) -> None:
    assert EnumPayload(value=value).model_dump(mode="json") == {"value": value.value}
