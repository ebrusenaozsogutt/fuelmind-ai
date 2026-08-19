"""Fuel-card configuration business rules; no authorization or consumption logic."""
# ruff: noqa
from datetime import date, time
from sqlalchemy.orm import Session
from app.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.commercial import FuelCardAllowedFuelType, FuelCardAllowedStation, FuelCardLimit, FuelCardUsageWindow
from app.repositories.fuel_card_repository import FuelCardConfigRepository, FuelCardRepository
from app.repositories.fuel_type_repository import FuelTypeRepository
from app.repositories.station_repository import StationRepository
from app.schemas.fuel_card import *  # noqa: F403
from app.services.vehicle_service import VehicleService
from app.services.audit_service import AuditService
from app.utils.enums import AuditAction, CardLimitType, CardStatus

class FuelCardService:
    def __init__(self,db:Session): self.db=db; self.repository=FuelCardRepository(db); self.vehicle_service=VehicleService(db)
    def get(self,id):
        e=self.repository.get(id)
        if e is None: raise NotFoundError("Fuel card not found.")
        return e
    def list(self,**kwargs): return self.repository.list(**kwargs)
    def by_unit(self,v):
        e=self.repository.by_unit(v.strip().upper())
        if e is None: raise NotFoundError("Fuel card not found.")
        return e
    def create(self,payload):
        v=payload.model_dump(); self._vehicle(v["vehicle_id"],v["is_active"]); self._unique(v); self._one_active(v["vehicle_id"],v["is_active"],v["status"]); return self._commit(lambda:self.repository.create(v))
    def update(self,id,payload,user_id=None,username=None):
        e=self.get(id); v=payload.model_dump(exclude_unset=True); combined={k:v.get(k,getattr(e,k)) for k in ("vehicle_id","card_code","unit_id","valid_from","valid_until","prepaid_balance","credit_limit","is_active","status")}
        if combined["valid_until"] is not None and combined["valid_until"] < combined["valid_from"]: raise BusinessRuleError("Card validity period is invalid.")
        self._vehicle(combined["vehicle_id"],combined["is_active"]); self._unique(combined,e.id); self._one_active(combined["vehicle_id"],combined["is_active"],combined["status"],e.id)
        if combined["vehicle_id"]!=e.vehicle_id and self.repository.has_config(e.id): raise BusinessRuleError("Fuel card with configuration cannot change vehicle.")
        old_status=e.status
        updated=self._commit(lambda:self.repository.update(e,v))
        if "status" in v or "is_active" in v:
            AuditService(self.db).record(action=AuditAction.STATUS_CHANGE,entity_type="FUEL_CARD",entity_id=e.id,user_id=user_id,username=username,old_values={"status":old_status},new_values={"status":updated.status,"is_active":updated.is_active},description="Fuel card status changed")
            self.db.commit()
        return updated
    def deactivate(self,id): return self._commit(lambda:self.repository.deactivate(self.get(id)))
    def _vehicle(self,id,active):
        vehicle=self.vehicle_service.get(id)
        if active and not vehicle.is_active: raise BusinessRuleError("Vehicle is inactive.")
        if active: self.vehicle_service._validate_hierarchy(vehicle.fleet_group_id,require_active=True)
    def _unique(self,v,exclude=None):
        for key,method,msg in (("card_code",self.repository.by_code,"Fuel card code already exists."),("unit_id",self.repository.by_unit,"Fuel card unit ID already exists.")):
            x=method(v[key])
            if x is not None and x.id!=exclude: raise ConflictError(msg)
    def _one_active(self,vehicle_id,active,status,exclude=None):
        if active and status==CardStatus.ACTIVE and self.repository.active_for_vehicle(vehicle_id,exclude): raise BusinessRuleError("Vehicle already has an active fuel card.")
    def _commit(self,op):
        try: e=op(); self.db.commit(); self.db.refresh(e); return e
        except Exception: self.db.rollback(); raise

class FuelCardConfigService:
    def __init__(self,db:Session): self.db=db; self.repo=FuelCardConfigRepository(db); self.cards=FuelCardService(db); self.stations=StationRepository(db); self.fuels=FuelTypeRepository(db)
    def _card(self,id,active=False):
        c=self.cards.get(id)
        if active and not c.is_active: raise BusinessRuleError("Fuel card is inactive.")
        return c
    def limits(self,card=None): return self.repo.list(FuelCardLimit,card)
    def create_limit(self,p,user_id=None,username=None):
        v=p.model_dump(); self._card(v["fuel_card_id"],v["is_active"]); self._limit_rules(v); entity=self._commit(lambda:self.repo.create(FuelCardLimit,v)); AuditService(self.db).record(action=AuditAction.CREATE,entity_type="FUEL_CARD_LIMIT",entity_id=entity.id,user_id=user_id,username=username,new_values={"quantity_limit_liters":entity.quantity_limit_liters,"limit_type":entity.limit_type},description="Fuel card limit created"); self.db.commit(); return entity
    def update_limit(self,id,p,user_id=None,username=None):
        e=self.repo.get(FuelCardLimit,id)
        if not e: raise NotFoundError("Fuel card limit not found.")
        v=p.model_dump(exclude_unset=True); c={k:v.get(k,getattr(e,k)) for k in ("fuel_card_id","limit_type","quantity_limit_liters","valid_from","valid_until","is_active")}; self._card(c["fuel_card_id"],c["is_active"]); self._limit_rules(c,e.id); old={key:getattr(e,key) for key in v}; entity=self._commit(lambda:self.repo.update(e,v)); AuditService(self.db).record(action=AuditAction.UPDATE,entity_type="FUEL_CARD_LIMIT",entity_id=entity.id,user_id=user_id,username=username,old_values=old,new_values={key:getattr(entity,key) for key in v},description="Fuel card limit changed"); self.db.commit(); return entity
    def deactivate_limit(self,id):
        e=self.repo.get(FuelCardLimit,id)
        if not e: raise NotFoundError("Fuel card limit not found.")
        return self._commit(lambda:self.repo.deactivate(e))
    def _limit_rules(self,v,exclude=None):
        if v["valid_until"] is not None and v["valid_from"] is not None and v["valid_until"]<v["valid_from"]: raise BusinessRuleError("Limit validity period is invalid.")
        if v["limit_type"]==CardLimitType.CUSTOM and (v["valid_from"] is None or v["valid_until"] is None): raise BusinessRuleError("Custom limits require a date range.")
        if not v["is_active"]: return
        for x in self.limits(v["fuel_card_id"]):
            if x.id==exclude or not x.is_active: continue
            if v["limit_type"]!=CardLimitType.CUSTOM and x.limit_type==v["limit_type"]: raise BusinessRuleError("Duplicate active card limit type.")
            if v["limit_type"]==CardLimitType.CUSTOM and x.limit_type==CardLimitType.CUSTOM and x.valid_from < v["valid_until"] and v["valid_from"] < x.valid_until: raise BusinessRuleError("Custom card limits overlap.")
    def permission(self,cls,card=None): return self.repo.list(cls,card)
    def add_station(self,p):
        v=p.model_dump(); self._card(v["fuel_card_id"],True)
        if self.stations.get(v["station_id"]) is None: raise NotFoundError("Station not found.")
        return self._add(FuelCardAllowedStation,v,"station_id")
    def add_fuel(self,p):
        v=p.model_dump(); self._card(v["fuel_card_id"],True)
        if self.fuels.get(v["fuel_type_id"]) is None: raise NotFoundError("Fuel type not found.")
        return self._add(FuelCardAllowedFuelType,v,"fuel_type_id")
    def _add(self,cls,v,key):
        if any(getattr(x,key)==v[key] for x in self.repo.list(cls,v["fuel_card_id"])): raise ConflictError("Duplicate fuel card permission.")
        return self._commit(lambda:self.repo.create(cls,v))
    def remove_permission(self,cls,id):
        e=self.repo.get(cls,id)
        if not e: raise NotFoundError("Fuel card permission not found.")
        self.db.delete(e); self.db.commit()
    def windows(self,card=None): return self.repo.list(FuelCardUsageWindow,card)
    def create_window(self,p):
        v=p.model_dump(); self._card(v["fuel_card_id"],v["is_active"]); self._window_rules(v); return self._commit(lambda:self.repo.create(FuelCardUsageWindow,v))
    def update_window(self,id,p):
        e=self.repo.get(FuelCardUsageWindow,id)
        if not e: raise NotFoundError("Usage window not found.")
        v=p.model_dump(exclude_unset=True); c={k:v.get(k,getattr(e,k)) for k in ("fuel_card_id","day_of_week","start_time","end_time","is_active")}; self._window_rules(c,e.id); return self._commit(lambda:self.repo.update(e,v))
    def deactivate_window(self,id):
        e=self.repo.get(FuelCardUsageWindow,id)
        if not e: raise NotFoundError("Usage window not found.")
        return self._commit(lambda:self.repo.deactivate(e))
    def _window_rules(self,v,exclude=None):
        self._card(v["fuel_card_id"],v["is_active"])
        if v["start_time"]>=v["end_time"]: raise BusinessRuleError("Overnight or empty usage windows are not supported.")
        if v["is_active"]:
            for x in self.windows(v["fuel_card_id"]):
                if x.id!=exclude and x.is_active and x.day_of_week==v["day_of_week"] and x.start_time<v["end_time"] and v["start_time"]<x.end_time: raise BusinessRuleError("Usage windows overlap.")
    def _commit(self,op):
        try: e=op(); self.db.commit(); self.db.refresh(e); return e
        except Exception: self.db.rollback(); raise
