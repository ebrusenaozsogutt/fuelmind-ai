"""Read-only live-history API contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.utils.enums import (
    ControllerStatus,
    ControllerType,
    NozzleStatus,
    PortStatus,
    PortType,
    ProbeStatus,
    SourceType,
)


class SensorHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    station_id: int
    tank_id: int | None
    pump_id: int | None
    simulation_run_id: int | None
    sequence_number: int | None
    reading_timestamp: datetime
    tank_level: float | None
    true_tank_level: float | None
    temperature: float | None
    water_level: float | None
    flow_rate: float | None
    pressure: float | None
    motor_current: float | None
    pump_temperature: float | None
    error_count: int
    working_duration: float | None
    data_quality_score: float
    quality_flags_json: list[str]
    source_type: SourceType
    communication_port_id: int | None = None


class ControllerLive(BaseModel):
    id: int
    station_id: int
    code: str
    name: str
    controller_type: ControllerType
    status: ControllerStatus
    is_active: bool
    last_communication_at: datetime | None


class CommunicationPortLive(BaseModel):
    id: int
    controller_id: int
    port_number: int
    name: str
    port_type: PortType
    protocol: str | None
    baud_rate: int | None
    status: PortStatus
    is_active: bool
    last_communication_at: datetime | None


class ProbeLive(BaseModel):
    id: int
    tank_id: int
    communication_port_id: int | None
    code: str
    name: str
    status: ProbeStatus
    is_active: bool
    last_communication_at: datetime | None
    fuel_height_mm: float | None = None
    fuel_volume_liters: float | None = None
    water_height_mm: float | None = None
    water_volume_liters: float | None = None
    temperature_celsius: float | None = None
    data_quality_score: float | None = None
    quality_flags: list[str] = Field(default_factory=list)
    reading_timestamp: datetime | None = None


class NozzleLive(BaseModel):
    id: int
    pump_id: int
    fuel_type_id: int
    code: str
    nozzle_number: int
    status: NozzleStatus
    totalizer_liters: float
    is_active: bool
    fuel_type_code: str
    fuel_type_name: str


class LiveStatusRead(BaseModel):
    station_id: int
    latest_sequence: int | None
    latest_reading_time: datetime | None
    tanks: list[SensorHistoryRead]
    pumps: list[SensorHistoryRead]
    controllers: list[ControllerLive] = Field(default_factory=list)
    ports: list[CommunicationPortLive] = Field(default_factory=list)
    probes: list[ProbeLive] = Field(default_factory=list)
    nozzles: list[NozzleLive] = Field(default_factory=list)
