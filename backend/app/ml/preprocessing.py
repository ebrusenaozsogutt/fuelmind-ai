"""Read-only selection of reliable sensor readings for future ML training."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Iterable

import pandas as pd
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.sensor_reading import SensorReading
from app.models.simulation_scenario import SimulationScenario
from app.services.monitoring_rules import DEFAULT_MONITORING_RULES
from app.utils.enums import SimulationTargetType, SourceType


# These are the quality problems already defined and penalized by Stage 7.
# Training must be more conservative than live display: a known bad reading
# should not redefine what a future unsupervised model considers normal.
CRITICAL_TRAINING_QUALITY_FLAGS = frozenset(DEFAULT_MONITORING_RULES.penalties or {})

RAW_TRAINING_COLUMNS = (
    "station_id",
    "pump_id",
    "tank_id",
    "simulation_run_id",
    "sequence_number",
    "reading_timestamp",
    "source_type",
    "tank_level",
    "true_tank_level",
    "temperature",
    "water_level",
    "flow_rate",
    "pressure",
    "motor_current",
    "pump_temperature",
    "error_count",
    "working_duration",
    "data_quality_score",
)

NUMERIC_TRAINING_COLUMNS = (
    "tank_level",
    "true_tank_level",
    "temperature",
    "water_level",
    "flow_rate",
    "pressure",
    "motor_current",
    "pump_temperature",
    "error_count",
    "working_duration",
    "data_quality_score",
)


@dataclass(frozen=True)
class TrainingDatasetSummary:
    """Selection counts and distributions for diagnosing a training dataset."""

    total_examined: int
    included: int
    excluded_quality: int
    excluded_anomaly: int
    excluded_scenario: int
    excluded_invalid: int
    start_time: datetime | None
    end_time: datetime | None
    source_type_distribution: dict[str, int]
    pump_distribution: dict[int, int]
    tank_distribution: dict[int, int]


@dataclass(frozen=True)
class TrainingDatasetResult:
    """The chronologically ordered raw dataset and its selection diagnostics."""

    dataframe: pd.DataFrame
    summary: TrainingDatasetSummary


class AnomalyTrainingDatasetBuilder:
    """Select trustworthy station readings without changing operational records.

    This class deliberately stops at raw-field selection. Feature engineering,
    model fitting, scoring, and model storage belong to later Stage 8 steps.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def build(
        self,
        *,
        station_id: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        source_types: Iterable[SourceType | str] | None = None,
        minimum_data_quality_score: float | None = None,
        exclude_known_anomalies: bool = True,
        exclude_active_scenarios: bool = True,
    ) -> TrainingDatasetResult:
        """Return clean, chronologically ordered raw readings for one station.

        SQL applies station, time, and source filters before rows enter
        application memory. Quality selection remains in the bounded record
        stream so the diagnostic summary can count every quality exclusion.
        Scenario intervals are fetched in one additional query and evaluated
        in memory because their target relationship is conditional (station,
        tank, or pump).
        """

        self._validate_inputs(station_id, start_time, end_time, minimum_data_quality_score)
        normalized_sources = self._normalize_source_types(source_types)
        minimum_quality = (
            float(DEFAULT_MONITORING_RULES.quality_minimum_score)
            if minimum_data_quality_score is None
            else minimum_data_quality_score
        )
        readings = list(
            self._db.scalars(
                self._readings_statement(
                    station_id=station_id,
                    start_time=start_time,
                    end_time=end_time,
                    source_types=normalized_sources,
                )
            )
        )
        scenarios = (
            self._active_scenario_candidates(station_id, start_time, end_time)
            if exclude_active_scenarios
            else []
        )

        accepted: list[SensorReading] = []
        excluded_quality = excluded_anomaly = excluded_scenario = excluded_invalid = 0
        for reading in readings:
            if (
                float(reading.data_quality_score) < minimum_quality
                or self._has_critical_quality_flag(reading)
            ):
                excluded_quality += 1
            elif exclude_known_anomalies and reading.is_anomaly:
                excluded_anomaly += 1
            elif exclude_active_scenarios and self._is_scenario_affected(reading, scenarios):
                excluded_scenario += 1
            elif not self._is_model_usable(reading):
                excluded_invalid += 1
            else:
                accepted.append(reading)

        records = [self._record(reading) for reading in accepted]
        dataframe = pd.DataFrame(records, columns=RAW_TRAINING_COLUMNS)
        if not dataframe.empty:
            dataframe = dataframe.sort_values(
                ["reading_timestamp", "sequence_number"], kind="stable", na_position="last"
            ).reset_index(drop=True)

        return TrainingDatasetResult(
            dataframe=dataframe,
            summary=TrainingDatasetSummary(
                total_examined=len(readings),
                included=len(accepted),
                excluded_quality=excluded_quality,
                excluded_anomaly=excluded_anomaly,
                excluded_scenario=excluded_scenario,
                excluded_invalid=excluded_invalid,
                start_time=start_time,
                end_time=end_time,
                source_type_distribution=self._distribution(dataframe, "source_type"),
                pump_distribution=self._distribution(dataframe, "pump_id"),
                tank_distribution=self._distribution(dataframe, "tank_id"),
            ),
        )

    @staticmethod
    def _validate_inputs(
        station_id: int,
        start_time: datetime | None,
        end_time: datetime | None,
        minimum_data_quality_score: float | None,
    ) -> None:
        if station_id <= 0:
            raise ValueError("station_id must be positive.")
        for name, value in (("start_time", start_time), ("end_time", end_time)):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} must be timezone-aware.")
        if start_time is not None and end_time is not None and start_time > end_time:
            raise ValueError("start_time must be earlier than or equal to end_time.")
        if minimum_data_quality_score is not None and not 0 <= minimum_data_quality_score <= 100:
            raise ValueError("minimum_data_quality_score must be between 0 and 100.")

    @staticmethod
    def _normalize_source_types(
        source_types: Iterable[SourceType | str] | None,
    ) -> tuple[SourceType, ...] | None:
        if source_types is None:
            return None
        try:
            normalized = tuple(SourceType(source) for source in source_types)
        except ValueError as exc:
            raise ValueError("source_types contains an unsupported source type.") from exc
        if not normalized:
            raise ValueError("source_types cannot be empty when supplied.")
        return normalized

    @staticmethod
    def _readings_statement(
        *,
        station_id: int,
        start_time: datetime | None,
        end_time: datetime | None,
        source_types: tuple[SourceType, ...] | None,
    ) -> Select[tuple[SensorReading]]:
        statement = select(SensorReading).where(SensorReading.station_id == station_id)
        if start_time is not None:
            statement = statement.where(SensorReading.reading_timestamp >= start_time)
        if end_time is not None:
            statement = statement.where(SensorReading.reading_timestamp <= end_time)
        if source_types is not None:
            statement = statement.where(SensorReading.source_type.in_(source_types))
        return statement.order_by(SensorReading.reading_timestamp, SensorReading.id)

    def _active_scenario_candidates(
        self,
        station_id: int,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> list[SimulationScenario]:
        statement = (
            select(SimulationScenario)
            .join(
                SensorReading,
                SensorReading.simulation_run_id == SimulationScenario.simulation_run_id,
            )
            .where(SensorReading.station_id == station_id)
            .distinct()
        )
        # Keep the candidate query bounded by the same requested window when
        # possible. The exact start/end overlap is checked below per reading.
        if end_time is not None:
            statement = statement.where(SimulationScenario.start_time <= end_time)
        return list(self._db.scalars(statement))

    @staticmethod
    def _has_critical_quality_flag(reading: SensorReading) -> bool:
        return bool(set(reading.quality_flags_json or ()) & CRITICAL_TRAINING_QUALITY_FLAGS)

    @staticmethod
    def _is_model_usable(reading: SensorReading) -> bool:
        timestamp = reading.reading_timestamp
        if not isinstance(timestamp, datetime):
            return False
        # PostgreSQL preserves the UTC offset. SQLite test fixtures and legacy
        # imports may materialize the same UTC value without it; `_utc` keeps
        # comparisons on a single UTC basis instead of rejecting usable data.
        values = [getattr(reading, column) for column in NUMERIC_TRAINING_COLUMNS]
        if any(value is not None and not isfinite(float(value)) for value in values):
            return False
        tank_signals = (reading.tank_level, reading.true_tank_level, reading.water_level)
        pump_signals = (reading.flow_rate, reading.pressure, reading.motor_current)
        return any(value is not None for value in (*tank_signals, *pump_signals))

    @staticmethod
    def _is_scenario_affected(
        reading: SensorReading, scenarios: list[SimulationScenario]
    ) -> bool:
        reading_time = AnomalyTrainingDatasetBuilder._utc(reading.reading_timestamp)
        for scenario in scenarios:
            if scenario.simulation_run_id != reading.simulation_run_id:
                continue
            start = AnomalyTrainingDatasetBuilder._utc(scenario.start_time)
            end = start + timedelta(minutes=scenario.duration_minutes)
            if not start <= reading_time < end:
                continue
            if scenario.target_type == SimulationTargetType.STATION and scenario.target_id == reading.station_id:
                return True
            if scenario.target_type == SimulationTargetType.TANK and scenario.target_id == reading.tank_id:
                return True
            if scenario.target_type == SimulationTargetType.PUMP and scenario.target_id == reading.pump_id:
                return True
        return False

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _record(reading: SensorReading) -> dict[str, object]:
        record = {column: getattr(reading, column) for column in RAW_TRAINING_COLUMNS}
        record["source_type"] = reading.source_type.value
        return record

    @staticmethod
    def _distribution(dataframe: pd.DataFrame, column: str) -> dict[object, int]:
        if dataframe.empty:
            return {}
        return dict(Counter(dataframe[column].dropna().tolist()))
