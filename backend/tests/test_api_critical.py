"""Critical API and inventory service behaviour tests."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import fuel_types, pumps, stations, tanks
from app.api.dependencies import require_admin
from app.database import get_db
from app.exceptions import BusinessRuleError
from app.main import app
from app.schemas.delivery import DeliveryCreate
from app.schemas.sale import SaleCreate
from app.services.delivery_service import DeliveryService
from app.services.pump_service import PumpService
from app.services.sale_service import SaleService
from app.services.tank_service import TankService
from app.utils.enums import PumpStatus


class FakeSession:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def refresh(self, _: object) -> None:
        pass


def test_capacity_exceeding_tank_level_is_rejected() -> None:
    with pytest.raises(BusinessRuleError):
        TankService._validate_levels(
            {
                "capacity_liters": Decimal("100"),
                "current_level_liters": Decimal("101"),
                "minimum_safe_level": Decimal("20"),
                "critical_level": Decimal("10"),
            }
        )


def test_pump_cannot_use_tank_from_another_station() -> None:
    service = PumpService(FakeSession())
    service.station_repository = SimpleNamespace(get=lambda _: object())
    service.tank_repository = SimpleNamespace(
        get=lambda _: SimpleNamespace(station_id=2)
    )
    with pytest.raises(BusinessRuleError):
        service._validate_relationship(1, 1)


def test_sale_reduces_tank_level_and_rejects_insufficient_stock() -> None:
    session = FakeSession()
    tank = SimpleNamespace(
        id=1,
        station_id=1,
        fuel_type_id=1,
        current_level_liters=Decimal("50"),
        is_active=True,
    )
    service = SaleService(session)
    service.station_repository = SimpleNamespace(
        get=lambda _: SimpleNamespace(is_active=True)
    )
    service.tank_repository = SimpleNamespace(get_for_update=lambda _: tank)
    service.pump_repository = SimpleNamespace(
        get=lambda _: SimpleNamespace(
            station_id=1, tank_id=1, is_active=True, status=PumpStatus.ACTIVE
        )
    )
    service.fuel_type_repository = SimpleNamespace(
        get=lambda _: SimpleNamespace(is_active=True)
    )
    service.repository = SimpleNamespace(
        create=lambda values: SimpleNamespace(
            id=1, created_at=datetime.now(timezone.utc), **values
        )
    )
    payload = SaleCreate(
        station_id=1,
        tank_id=1,
        pump_id=1,
        fuel_type_id=1,
        sale_timestamp=datetime.now(timezone.utc),
        quantity_liters=Decimal("10"),
        unit_price=Decimal("2"),
        duration_seconds=1,
    )
    sale = service.create(payload)
    assert tank.current_level_liters == Decimal("40")
    assert sale.total_amount == Decimal("20.00")
    assert sale.level_before == Decimal("50")
    assert sale.level_after == Decimal("40")
    payload.quantity_liters = Decimal("60")
    with pytest.raises(BusinessRuleError, match="enough fuel"):
        service.create(payload)
    assert tank.current_level_liters == Decimal("40")


def test_delivery_increases_tank_level_and_blocks_capacity_overflow() -> None:
    session = FakeSession()
    tank = SimpleNamespace(
        id=1,
        current_level_liters=Decimal("50"),
        capacity_liters=Decimal("100"),
        is_active=True,
    )
    service = DeliveryService(session)
    service.tank_repository = SimpleNamespace(get_for_update=lambda _: tank)
    service.repository = SimpleNamespace(
        create=lambda values: SimpleNamespace(
            id=1, created_at=datetime.now(timezone.utc), **values
        )
    )
    payload = DeliveryCreate(
        tank_id=1,
        delivery_timestamp=datetime.now(timezone.utc),
        quantity_liters=Decimal("25"),
        supplier_name="Supplier",
    )
    service.create(payload)
    assert tank.current_level_liters == Decimal("75")
    payload.quantity_liters = Decimal("30")
    with pytest.raises(BusinessRuleError, match="exceed tank capacity"):
        service.create(payload)
    assert tank.current_level_liters == Decimal("75")


def test_operator_cannot_access_admin_endpoint() -> None:
    def deny_admin() -> None:
        raise HTTPException(status_code=403, detail="Insufficient permissions.")

    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[require_admin] = deny_admin
    with TestClient(app) as client:
        response = client.post(
            "/api/fuel-types", json={"name": "Diesel", "code": "DSL"}
        )
    app.dependency_overrides.clear()
    assert response.status_code == 403


def test_fuel_type_creation_endpoint_uses_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeFuelTypeService:
        def __init__(self, _: object) -> None:
            pass

        def create(self, _: object) -> dict[str, object]:
            return {
                "id": 1,
                "name": "Diesel",
                "code": "DSL",
                "unit": "LITER",
                "is_active": True,
            }

    monkeypatch.setattr(fuel_types, "FuelTypeService", FakeFuelTypeService)
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[require_admin] = lambda: object()
    with TestClient(app) as client:
        response = client.post(
            "/api/fuel-types", json={"name": "Diesel", "code": "dsl"}
        )
    app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["code"] == "DSL"


def test_station_tank_and_pump_creation_endpoints_use_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeStationService:
        def __init__(self, _: object) -> None:
            pass

        def create(self, _: object) -> dict[str, object]:
            return {
                "id": 1,
                "code": "ST-1",
                "name": "Station",
                "city": "City",
                "district": "District",
                "address": "Address",
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
            }

    class FakeTankService:
        def __init__(self, _: object) -> None:
            pass

        def create(self, _: object) -> dict[str, object]:
            return {
                "id": 1,
                "station_id": 1,
                "fuel_type_id": 1,
                "code": "T-1",
                "capacity_liters": "100",
                "current_level_liters": "50",
                "minimum_safe_level": "20",
                "critical_level": "10",
                "water_level": "0",
                "temperature": None,
                "sensor_status": "ACTIVE",
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
            }

    class FakePumpService:
        def __init__(self, _: object) -> None:
            pass

        def create(self, _: object) -> dict[str, object]:
            return {
                "id": 1,
                "station_id": 1,
                "tank_id": 1,
                "code": "P-1",
                "status": "IDLE",
                "nominal_flow_rate": "10",
                "minimum_flow_rate": "1",
                "maximum_motor_current": "5",
                "maximum_pressure": "3",
                "last_maintenance_at": None,
                "total_working_hours": "0",
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
            }

    monkeypatch.setattr(stations, "StationService", FakeStationService)
    monkeypatch.setattr(tanks, "TankService", FakeTankService)
    monkeypatch.setattr(pumps, "PumpService", FakePumpService)
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[require_admin] = lambda: object()
    with TestClient(app) as client:
        station_response = client.post(
            "/api/stations",
            json={
                "code": "st-1",
                "name": "Station",
                "city": "City",
                "district": "District",
                "address": "Address",
            },
        )
        tank_response = client.post(
            "/api/stations/1/tanks",
            json={
                "station_id": 1,
                "fuel_type_id": 1,
                "code": "t-1",
                "capacity_liters": "100",
                "current_level_liters": "50",
                "minimum_safe_level": "20",
                "critical_level": "10",
            },
        )
        pump_response = client.post(
            "/api/stations/1/pumps",
            json={
                "station_id": 1,
                "tank_id": 1,
                "code": "p-1",
                "nominal_flow_rate": "10",
                "minimum_flow_rate": "1",
                "maximum_motor_current": "5",
                "maximum_pressure": "3",
            },
        )
    app.dependency_overrides.clear()
    assert (
        station_response.status_code
        == tank_response.status_code
        == pump_response.status_code
        == 201
    )
