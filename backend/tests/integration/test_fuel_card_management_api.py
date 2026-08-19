"""Focused integration coverage for fuel-card management."""
# ruff: noqa
from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from app.api.dependencies import require_admin, require_operator_or_admin
from app.database import Base, get_db
from app.main import app
from app.models.commercial import Customer, Fleet, FleetGroup, FuelCard, FuelCardAllowedFuelType, FuelCardAllowedStation, FuelCardLimit, FuelCardUsageWindow, Vehicle
from app.models.fuel_type import FuelType
from app.models.station import Station
from app.models.audit_log import AuditLog

@compiles(JSONB,"sqlite")
def _compile_jsonb_sqlite(_, __, **___): return "JSON"

TABLES=[Customer.__table__,Fleet.__table__,FleetGroup.__table__,Vehicle.__table__,FuelCard.__table__,FuelCardLimit.__table__,FuelCardAllowedStation.__table__,FuelCardAllowedFuelType.__table__,FuelCardUsageWindow.__table__,Station.__table__,FuelType.__table__,AuditLog.__table__]
@pytest.fixture
def api():
    e=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool); Base.metadata.create_all(e,tables=TABLES); f=sessionmaker(bind=e,expire_on_commit=False)
    app.dependency_overrides[get_db]=lambda:f(); app.dependency_overrides[require_admin]=lambda:object(); app.dependency_overrides[require_operator_or_admin]=lambda:object()
    try:
        with TestClient(app) as c: yield c,f
    finally:
        app.dependency_overrides.clear(); Base.metadata.drop_all(e,tables=list(reversed(TABLES))); e.dispose()
def vehicle(c):
    x=c.post("/api/customers",json={"code":"C","name":"C","customer_type":"COMPANY"}).json(); f=c.post("/api/fleets",json={"customer_id":x["id"],"code":"F","name":"F"}).json(); g=c.post("/api/fleet-groups",json={"fleet_id":f["id"],"code":"G","name":"G"}).json(); return c.post("/api/vehicles",json={"fleet_group_id":g["id"],"plate":"42 A 1"}).json()
def test_card_limits_permissions_and_windows(api):
    c,f=api; v=vehicle(c); p={"vehicle_id":v["id"],"card_code":" card-1 ","unit_id":" unit-1 ","display_name":" Card ","valid_from":date.today().isoformat(),"payment_type":"PREPAID"}; card=c.post("/api/fuel-cards",json=p); assert card.status_code==201; card=card.json(); assert card["card_code"]=="CARD-1" and c.post("/api/fuel-cards",json=p).status_code==409
    assert c.post("/api/fuel-card-limits",json={"fuel_card_id":card["id"],"limit_type":"DAILY","quantity_limit_liters":"10"}).status_code==201
    assert c.post("/api/fuel-card-limits",json={"fuel_card_id":card["id"],"limit_type":"DAILY","quantity_limit_liters":"20"}).status_code==400
    assert c.post("/api/fuel-card-usage-windows",json={"fuel_card_id":card["id"],"day_of_week":0,"start_time":"06:00","end_time":"12:00"}).status_code==201
    assert c.post("/api/fuel-card-usage-windows",json={"fuel_card_id":card["id"],"day_of_week":0,"start_time":"10:00","end_time":"15:00"}).status_code==400
    s=f(); station=Station(code="S",name="S",city="C",district="D",address="A"); fuel=FuelType(name="Diesel",code="DSL"); s.add_all([station,fuel]); s.commit()
    assert c.post("/api/fuel-card-allowed-stations",json={"fuel_card_id":card["id"],"station_id":station.id}).status_code==201
    assert c.post("/api/fuel-card-allowed-fuel-types",json={"fuel_card_id":card["id"],"fuel_type_id":fuel.id}).status_code==201
    assert c.get(f"/api/fuel-cards/by-unit/{card['unit_id'].lower()}").status_code==200
    assert c.delete(f"/api/fuel-cards/{card['id']}").status_code==204
    card2=c.post("/api/fuel-cards",json={**p,"card_code":"CARD-2","unit_id":"UNIT-2"}).json()
    assert c.post("/api/fuel-card-limits",json={"fuel_card_id":card2["id"],"limit_type":"PER_TRANSACTION","quantity_limit_liters":"1"}).status_code==201
    assert c.post("/api/fuel-card-allowed-stations",json={"fuel_card_id":card2["id"],"station_id":station.id}).status_code==201
    assert c.post("/api/fuel-card-allowed-fuel-types",json={"fuel_card_id":card2["id"],"fuel_type_id":fuel.id}).status_code==201
    auth=c.post("/api/fuel-cards/authorize",json={"unit_id":"unit-2","vehicle_id":v["id"],"station_id":station.id,"fuel_type_id":fuel.id,"requested_quantity_liters":"1"})
    assert auth.status_code==200 and auth.json()["decision_code"]=="AUTHORIZED"; s.close()

def test_card_limit_change_creates_audit(api):
    c,f=api; v=vehicle(c); card=c.post("/api/fuel-cards",json={"vehicle_id":v["id"],"card_code":"AUDIT-CARD","unit_id":"AUDIT-UNIT","display_name":"Audit Card","valid_from":date.today().isoformat(),"payment_type":"PREPAID"}).json()
    limit=c.post("/api/fuel-card-limits",json={"fuel_card_id":card["id"],"limit_type":"DAILY","quantity_limit_liters":"10"}).json()
    response=c.put(f"/api/fuel-card-limits/{limit['id']}",json={"quantity_limit_liters":"20"})
    assert response.status_code==200
    session=f(); audit=session.query(AuditLog).filter_by(entity_type="FUEL_CARD_LIMIT",entity_id=limit["id"],action="UPDATE").one(); assert audit.old_values_json=={"quantity_limit_liters":"10.000"}; assert audit.new_values_json=={"quantity_limit_liters":"20.000"}; session.close()
