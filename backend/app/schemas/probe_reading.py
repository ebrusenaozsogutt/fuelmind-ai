"""Read-only probe measurement API schema."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.utils.enums import SourceType


class ProbeReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    probe_id: int
    tank_id: int
    simulation_run_id: int | None
    sequence_number: int | None
    reading_timestamp: datetime
    fuel_height_mm: Decimal | None
    fuel_volume_liters: Decimal | None
    water_height_mm: Decimal | None
    water_volume_liters: Decimal | None
    temperature_celsius: Decimal | None
    data_quality_score: Decimal
    quality_flags_json: list[str]
    source_type: SourceType
    created_at: datetime
