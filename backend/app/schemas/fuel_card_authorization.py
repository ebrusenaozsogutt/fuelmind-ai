"""Read-only fuel-card authorization contracts."""
# ruff: noqa
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.utils.enums import CardAuthorizationDecision, CardLimitType
class FuelCardAuthorizationRequest(BaseModel):
    unit_id: str
    vehicle_id: int = Field(gt=0)
    station_id: int = Field(gt=0)
    fuel_type_id: int = Field(gt=0)
    requested_quantity_liters: Decimal
    requested_at: datetime | None = None
class CardLimitEvaluation(BaseModel):
    limit_id:int; limit_type:CardLimitType; limit_liters:Decimal; used_liters:Decimal; requested_liters:Decimal; remaining_before_liters:Decimal; remaining_after_liters:Decimal; passed:bool; period_start:datetime; period_end:datetime
class FuelCardAuthorizationResult(BaseModel):
    authorized:bool; decision_code:CardAuthorizationDecision; message:str; fuel_card_id:int|None=None; unit_id:str; vehicle_id:int; station_id:int; fuel_type_id:int; requested_quantity_liters:Decimal; evaluated_at:datetime; limit_results:list[CardLimitEvaluation]=[]
