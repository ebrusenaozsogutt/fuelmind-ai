"""Typed, version-tolerant live AI result published to operational clients."""

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum


class LiveAiState(str, Enum):
    READY = "READY"
    WARMING_UP = "WARMING_UP"
    NO_ACTIVE_MODEL = "NO_ACTIVE_MODEL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class LiveAnomalyResult:
    entity_type: str
    entity_id: int
    station_id: int
    timestamp: datetime
    ai_state: LiveAiState
    risk_score: float | None = None
    risk_level: str | None = None
    decision_source: str = "NONE"
    severity: str | None = None
    anomaly_type: str | None = None
    model_outlier: bool | None = None
    triggered_rules: tuple[str, ...] = ()
    # Keep the numeric evidence intact.  The alarm center needs more than the
    # rendered sentence to show the actual value, learned reference and drift.
    findings: tuple[dict[str, object], ...] = ()
    probable_causes: tuple[str, ...] = ()
    recommended_checks: tuple[str, ...] = ()
    data_quality_note: str | None = None
    model_version: str | None = None
    decision_function: float | None = None

    @property
    def is_anomaly(self) -> bool:
        return self.decision_source not in {"NONE", "WARMING_UP", "NO_ACTIVE_MODEL", "UNAVAILABLE"}

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        payload["ai_state"] = self.ai_state.value
        payload["is_anomaly"] = self.is_anomaly
        return payload
