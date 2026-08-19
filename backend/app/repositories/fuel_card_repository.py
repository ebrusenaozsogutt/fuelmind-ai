"""Queries for fuel cards and their configuration records."""
# ruff: noqa
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models.commercial import FuelCard, FuelCardAllowedFuelType, FuelCardAllowedStation, FuelCardLimit, FuelCardUsageWindow
from app.utils.enums import CardLimitType, CardStatus, PaymentType

class FuelCardRepository:
    def __init__(self, db: Session): self.db = db
    def get(self, id: int): return self.db.get(FuelCard, id)
    def by_unit_for_update(self, v: str): return self.db.scalar(select(FuelCard).where(FuelCard.unit_id == v).with_for_update())
    def by_code(self, v: str): return self.db.scalar(select(FuelCard).where(FuelCard.card_code == v))
    def by_unit(self, v: str): return self.db.scalar(select(FuelCard).where(FuelCard.unit_id == v))
    def list(self, vehicle_id=None, status=None, payment_type=None, is_active=None, search=None):
        q=select(FuelCard)
        if vehicle_id is not None: q=q.where(FuelCard.vehicle_id==vehicle_id)
        if status is not None: q=q.where(FuelCard.status==status)
        if payment_type is not None: q=q.where(FuelCard.payment_type==payment_type)
        if is_active is not None: q=q.where(FuelCard.is_active==is_active)
        if search: q=q.where(or_(FuelCard.card_code.ilike(f"%{search}%"), FuelCard.unit_id.ilike(f"%{search}%"), FuelCard.display_name.ilike(f"%{search}%")))
        return list(self.db.scalars(q.order_by(FuelCard.card_code)))
    def create(self,v): e=FuelCard(**v); self.db.add(e); self.db.flush(); return e
    def update(self,e,v): [setattr(e,k,x) for k,x in v.items()]; self.db.flush(); return e
    def deactivate(self,e): e.is_active=False; self.db.flush(); return e
    def active_for_vehicle(self, vehicle_id, exclude=None):
        q=select(FuelCard).where(FuelCard.vehicle_id==vehicle_id,FuelCard.is_active.is_(True),FuelCard.status==CardStatus.ACTIVE)
        return next((x for x in self.db.scalars(q) if x.id != exclude),None)
    def has_config(self,id): return any([self.db.scalar(select(FuelCardLimit.id).where(FuelCardLimit.fuel_card_id==id).limit(1)),self.db.scalar(select(FuelCardAllowedStation.id).where(FuelCardAllowedStation.fuel_card_id==id).limit(1)),self.db.scalar(select(FuelCardAllowedFuelType.id).where(FuelCardAllowedFuelType.fuel_card_id==id).limit(1)),self.db.scalar(select(FuelCardUsageWindow.id).where(FuelCardUsageWindow.fuel_card_id==id).limit(1))])

class FuelCardConfigRepository:
    def __init__(self,db: Session): self.db=db
    def get(self, cls,id): return self.db.get(cls,id)
    def list(self, cls, card_id=None):
        q=select(cls)
        if card_id is not None: q=q.where(cls.fuel_card_id==card_id)
        return list(self.db.scalars(q))
    def create(self,cls,v): e=cls(**v); self.db.add(e); self.db.flush(); return e
    def update(self,e,v): [setattr(e,k,x) for k,x in v.items()]; self.db.flush(); return e
    def deactivate(self,e): e.is_active=False; self.db.flush(); return e
    def remove(self,e): self.db.delete(e); self.db.flush()
