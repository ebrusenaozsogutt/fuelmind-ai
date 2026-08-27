"""Deterministic, read-only card authorization decisions."""
# ruff: noqa
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.commercial import FuelCardAllowedFuelType, FuelCardAllowedStation, FuelCardLimit, FuelCardUsageWindow
from app.models.sale import Sale
from app.models.station import Station
from app.models.fuel_type import FuelType
from app.repositories.fuel_card_repository import FuelCardRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.repositories.fleet_group_repository import FleetGroupRepository
from app.repositories.fleet_repository import FleetRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.fuel_card_authorization import CardLimitEvaluation, FuelCardAuthorizationRequest, FuelCardAuthorizationResult
from app.utils.datetime_utils import utc_now
from app.utils.enums import CardAuthorizationDecision as D, CardLimitType, CardStatus, SaleStatus

class FuelCardAuthorizationService:
 def __init__(self,db:Session): self.db=db; self.cards=FuelCardRepository(db); self.vehicles=VehicleRepository(db); self.groups=FleetGroupRepository(db); self.fleets=FleetRepository(db); self.customers=CustomerRepository(db)
 def authorize(self,r:FuelCardAuthorizationRequest):
  now=r.requested_at or utc_now(); now=now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
  base=dict(unit_id=r.unit_id.strip().upper(),vehicle_id=r.vehicle_id,station_id=r.station_id,fuel_type_id=r.fuel_type_id,requested_quantity_liters=r.requested_quantity_liters,evaluated_at=now)
  if r.requested_quantity_liters<=0:return self._result(False,D.INVALID_QUANTITY,"Requested quantity must be positive.",None,base)
  card=self.cards.by_unit(base["unit_id"])
  if not card:return self._result(False,D.CARD_NOT_FOUND,"Fuel card not found.",None,base)
  if not card.is_active:return self._result(False,D.CARD_INACTIVE,"Fuel card is inactive.",card.id,base)
  statuses={CardStatus.PASSIVE:D.CARD_PASSIVE,CardStatus.BLOCKED:D.CARD_BLOCKED,CardStatus.EXPIRED:D.CARD_EXPIRED}
  if card.status in statuses:return self._result(False,statuses[card.status],"Fuel card status does not allow use.",card.id,base)
  day=now.date()
  if day<card.valid_from:return self._result(False,D.CARD_NOT_YET_VALID,"Fuel card is not yet valid.",card.id,base)
  if card.valid_until and day>card.valid_until:return self._result(False,D.CARD_EXPIRED,"Fuel card is expired.",card.id,base)
  vehicle=self.vehicles.get(r.vehicle_id)
  if not vehicle:return self._result(False,D.VEHICLE_NOT_FOUND,"Vehicle not found.",card.id,base)
  if card.vehicle_id!=vehicle.id:return self._result(False,D.VEHICLE_MISMATCH,"Fuel card does not belong to this vehicle.",card.id,base)
  if not vehicle.is_active:return self._result(False,D.VEHICLE_INACTIVE,"Vehicle is inactive.",card.id,base)
  g=self.groups.get(vehicle.fleet_group_id); f=self.fleets.get(g.fleet_id) if g else None; c=self.customers.get(f.customer_id) if f else None
  if not g or not f or not c or not g.is_active or not f.is_active or not c.is_active:return self._result(False,D.VEHICLE_HIERARCHY_INACTIVE,"Vehicle hierarchy is inactive.",card.id,base)
  if not self.db.get(Station,r.station_id):return self._result(False,D.STATION_NOT_FOUND,"Station not found.",card.id,base)
  if not self.db.scalar(select(FuelCardAllowedStation.id).where(FuelCardAllowedStation.fuel_card_id==card.id,FuelCardAllowedStation.station_id==r.station_id)):return self._result(False,D.STATION_NOT_ALLOWED,"Station is not allowed.",card.id,base)
  if not self.db.get(FuelType,r.fuel_type_id):return self._result(False,D.FUEL_TYPE_NOT_FOUND,"Fuel type not found.",card.id,base)
  if not self.db.scalar(select(FuelCardAllowedFuelType.id).where(FuelCardAllowedFuelType.fuel_card_id==card.id,FuelCardAllowedFuelType.fuel_type_id==r.fuel_type_id)):return self._result(False,D.FUEL_NOT_ALLOWED,"Fuel type is not allowed.",card.id,base)
  windows=list(self.db.scalars(select(FuelCardUsageWindow).where(FuelCardUsageWindow.fuel_card_id==card.id,FuelCardUsageWindow.is_active.is_(True))))
  if windows:
   day_windows=[w for w in windows if w.day_of_week==now.weekday()]
   previous_day=(now.weekday()-1)%7
   overnight_windows=[w for w in windows if w.day_of_week==previous_day and w.end_time<w.start_time]
   if not day_windows and not overnight_windows:return self._result(False,D.DAY_NOT_ALLOWED,"Day is not allowed.",card.id,base)
   current_time=now.timetz().replace(tzinfo=None)
   def _within(w):
    return w.start_time<=current_time<w.end_time if w.end_time>w.start_time else current_time>=w.start_time or current_time<w.end_time
   if not any(_within(w) for w in day_windows+overnight_windows):return self._result(False,D.TIME_NOT_ALLOWED,"Time is not allowed.",card.id,base)
  results=[]; failures=[]
  order={CardLimitType.PER_TRANSACTION:0,CardLimitType.DAILY:1,CardLimitType.WEEKLY:2,CardLimitType.MONTHLY:3,CardLimitType.CUSTOM:4}
  for limit in sorted(self.db.scalars(select(FuelCardLimit).where(FuelCardLimit.fuel_card_id==card.id,FuelCardLimit.is_active.is_(True))),key=lambda x:order[x.limit_type]):
   period=self._period(limit,now)
   if period is None:continue
   start,end=period; used=Decimal("0") if limit.limit_type==CardLimitType.PER_TRANSACTION else self._sum(card.id,start,end); after=limit.quantity_limit_liters-used-r.requested_quantity_liters; passed=after>=0
   results.append(CardLimitEvaluation(limit_id=limit.id,limit_type=limit.limit_type,limit_liters=limit.quantity_limit_liters,used_liters=used,requested_liters=r.requested_quantity_liters,remaining_before_liters=limit.quantity_limit_liters-used,remaining_after_liters=after,passed=passed,period_start=start,period_end=end))
   if not passed:failures.append(limit.limit_type)
  code={CardLimitType.PER_TRANSACTION:D.TRANSACTION_LIMIT_EXCEEDED,CardLimitType.DAILY:D.DAILY_LIMIT_EXCEEDED,CardLimitType.WEEKLY:D.WEEKLY_LIMIT_EXCEEDED,CardLimitType.MONTHLY:D.MONTHLY_LIMIT_EXCEEDED,CardLimitType.CUSTOM:D.CUSTOM_LIMIT_EXCEEDED}
  if failures:return self._result(False,code[failures[0]],"Requested quantity exceeds a card limit.",card.id,base,results)
  return self._result(True,D.AUTHORIZED,"Fuel card is authorized.",card.id,base,results)
 def _period(self,l,at):
  d=at.date(); tz=at.tzinfo
  if l.limit_type==CardLimitType.PER_TRANSACTION:
   if l.valid_from and d<l.valid_from:return None
   if l.valid_until and d>=l.valid_until:return None
   return datetime.combine(l.valid_from or d,time.min,tz),datetime.combine(l.valid_until or (d+timedelta(days=1)),time.min,tz)
  if l.limit_type==CardLimitType.DAILY:s=d
  elif l.limit_type==CardLimitType.WEEKLY:s=d-timedelta(days=d.weekday())
  elif l.limit_type==CardLimitType.MONTHLY:s=d.replace(day=1)
  else:
   if not(l.valid_from<=d<l.valid_until):return None
   return datetime.combine(l.valid_from,time.min,tz),datetime.combine(l.valid_until,time.min,tz)
  e=s+timedelta(days=1) if l.limit_type==CardLimitType.DAILY else (s+timedelta(days=7) if l.limit_type==CardLimitType.WEEKLY else (s.replace(year=s.year+1,month=1) if s.month==12 else s.replace(month=s.month+1)))
  return datetime.combine(s,time.min,tz),datetime.combine(e,time.min,tz)
 def _sum(self,card,start,end):return self.db.scalar(select(func.coalesce(func.sum(Sale.quantity_liters),0)).where(Sale.fuel_card_id==card,Sale.sale_status==SaleStatus.COMPLETED,Sale.sale_timestamp>=start,Sale.sale_timestamp<end)) or Decimal("0")
 def _result(self,ok,code,msg,card,base,limits=[]):return FuelCardAuthorizationResult(authorized=ok,decision_code=code,message=msg,fuel_card_id=card,limit_results=limits,**base)
