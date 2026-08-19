"""Fuel-card and configuration management endpoints."""
# ruff: noqa
from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import get_db
from app.models.commercial import FuelCardAllowedFuelType, FuelCardAllowedStation
from app.models.user import User
from app.schemas.fuel_card import *  # noqa: F403
from app.schemas.fuel_card_authorization import FuelCardAuthorizationRequest, FuelCardAuthorizationResult
from app.services.fuel_card_service import FuelCardConfigService, FuelCardService
from app.services.fuel_card_authorization_service import FuelCardAuthorizationService
from app.utils.enums import CardStatus, PaymentType
router=APIRouter(tags=["Fuel Cards","Fuel Card Limits","Fuel Card Permissions"])

@router.get("/fuel-cards",response_model=list[FuelCardRead])
def cards(db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)],vehicle_id:int|None=None,status:CardStatus|None=None,payment_type:PaymentType|None=None,is_active:bool|None=None,search:str|None=None): return FuelCardService(db).list(vehicle_id=vehicle_id,status=status,payment_type=payment_type,is_active=is_active,search=search)
@router.post("/fuel-cards",response_model=FuelCardRead,status_code=status.HTTP_201_CREATED)
def add_card(p:FuelCardCreate,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): return FuelCardService(db).create(p)
@router.get("/fuel-cards/by-unit/{unit_id}",response_model=FuelCardRead)
def by_unit(unit_id:str,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)]): return FuelCardService(db).by_unit(unit_id)
@router.post("/fuel-cards/authorize",response_model=FuelCardAuthorizationResult)
def authorize(p:FuelCardAuthorizationRequest,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)]): return FuelCardAuthorizationService(db).authorize(p)
@router.get("/fuel-cards/{card_id}",response_model=FuelCardRead)
def card(card_id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)]): return FuelCardService(db).get(card_id)
@router.put("/fuel-cards/{card_id}",response_model=FuelCardRead)
def update_card(card_id:int,p:FuelCardUpdate,db:Annotated[Session,Depends(get_db)],user:Annotated[User,Depends(require_admin)]): return FuelCardService(db).update(card_id,p,getattr(user,"id",None),getattr(user,"username",None))
@router.delete("/fuel-cards/{card_id}",status_code=204)
def deactivate_card(card_id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): FuelCardService(db).deactivate(card_id)
@router.get("/vehicles/{vehicle_id}/fuel-cards",response_model=list[FuelCardRead])
def vehicle_cards(vehicle_id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)]): return FuelCardService(db).list(vehicle_id=vehicle_id)

@router.get("/fuel-card-limits",response_model=list[FuelCardLimitRead])
def limits(db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)],fuel_card_id:int|None=None): return FuelCardConfigService(db).limits(fuel_card_id)
@router.post("/fuel-card-limits",response_model=FuelCardLimitRead,status_code=201)
def add_limit(p:FuelCardLimitCreate,db:Annotated[Session,Depends(get_db)],user:Annotated[User,Depends(require_admin)]): return FuelCardConfigService(db).create_limit(p,getattr(user,"id",None),getattr(user,"username",None))
@router.put("/fuel-card-limits/{id}",response_model=FuelCardLimitRead)
def update_limit(id:int,p:FuelCardLimitUpdate,db:Annotated[Session,Depends(get_db)],user:Annotated[User,Depends(require_admin)]): return FuelCardConfigService(db).update_limit(id,p,getattr(user,"id",None),getattr(user,"username",None))
@router.delete("/fuel-card-limits/{id}",status_code=204)
def deactivate_limit(id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): FuelCardConfigService(db).deactivate_limit(id)
@router.get("/fuel-cards/{card_id}/limits",response_model=list[FuelCardLimitRead])
def card_limits(card_id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)]): return FuelCardConfigService(db).limits(card_id)

@router.post("/fuel-card-allowed-stations",response_model=FuelCardAllowedStationRead,status_code=201)
def add_station(p:FuelCardAllowedStationCreate,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): return FuelCardConfigService(db).add_station(p)
@router.delete("/fuel-card-allowed-stations/{id}",status_code=204)
def del_station(id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): FuelCardConfigService(db).remove_permission(FuelCardAllowedStation,id)
@router.get("/fuel-cards/{card_id}/allowed-stations",response_model=list[FuelCardAllowedStationRead])
def stations(card_id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)]): return FuelCardConfigService(db).permission(FuelCardAllowedStation,card_id)
@router.post("/fuel-card-allowed-fuel-types",response_model=FuelCardAllowedFuelTypeRead,status_code=201)
def add_fuel(p:FuelCardAllowedFuelTypeCreate,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): return FuelCardConfigService(db).add_fuel(p)
@router.delete("/fuel-card-allowed-fuel-types/{id}",status_code=204)
def del_fuel(id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): FuelCardConfigService(db).remove_permission(FuelCardAllowedFuelType,id)
@router.get("/fuel-cards/{card_id}/allowed-fuel-types",response_model=list[FuelCardAllowedFuelTypeRead])
def fuels(card_id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)]): return FuelCardConfigService(db).permission(FuelCardAllowedFuelType,card_id)

@router.get("/fuel-card-usage-windows",response_model=list[FuelCardUsageWindowRead])
def windows(db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)],fuel_card_id:int|None=None): return FuelCardConfigService(db).windows(fuel_card_id)
@router.post("/fuel-card-usage-windows",response_model=FuelCardUsageWindowRead,status_code=201)
def add_window(p:FuelCardUsageWindowCreate,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): return FuelCardConfigService(db).create_window(p)
@router.put("/fuel-card-usage-windows/{id}",response_model=FuelCardUsageWindowRead)
def update_window(id:int,p:FuelCardUsageWindowUpdate,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): return FuelCardConfigService(db).update_window(id,p)
@router.delete("/fuel-card-usage-windows/{id}",status_code=204)
def deactivate_window(id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_admin)]): FuelCardConfigService(db).deactivate_window(id)
@router.get("/fuel-cards/{card_id}/usage-windows",response_model=list[FuelCardUsageWindowRead])
def card_windows(card_id:int,db:Annotated[Session,Depends(get_db)],_:Annotated[User,Depends(require_operator_or_admin)]): return FuelCardConfigService(db).windows(card_id)
