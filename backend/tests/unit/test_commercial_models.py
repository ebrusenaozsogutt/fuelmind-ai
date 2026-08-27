"""Model-level coverage for Stage 10 commercial domain foundations."""

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.commercial import (
    Customer,
    CustomerAuthorizedPerson,
    Driver,
    DriverVehicleAssignment,
    Fleet,
    FleetGroup,
    FuelCard,
    FuelCardAllowedFuelType,
    FuelCardAllowedStation,
    FuelCardLimit,
    FuelCardUsageWindow,
    FuelPrice,
    Vehicle,
)
from app.models.fuel_type import FuelType
from app.models.nozzle import Nozzle
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.station import Station
from app.models.tank import Tank
from app.models.user import User
from app.utils.datetime_utils import utc_now
from app.utils.enums import (
    CardLimitType,
    CustomerType,
    DriverAssignmentStatus,
    PaymentType,
    PumpStatus,
    SaleStatus,
)


_TABLES = [
    User.__table__,
    Station.__table__,
    FuelType.__table__,
    Tank.__table__,
    Pump.__table__,
    Nozzle.__table__,
    Customer.__table__,
    CustomerAuthorizedPerson.__table__,
    Fleet.__table__,
    FleetGroup.__table__,
    Vehicle.__table__,
    Driver.__table__,
    DriverVehicleAssignment.__table__,
    FuelCard.__table__,
    FuelCardLimit.__table__,
    FuelCardAllowedStation.__table__,
    FuelCardAllowedFuelType.__table__,
    FuelCardUsageWindow.__table__,
    FuelPrice.__table__,
    Sale.__table__,
]


@pytest.fixture
def commercial_session() -> Session:
    """Provide an isolated, constraint-enforcing commercial test database."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=_TABLES)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(_TABLES)))
        engine.dispose()


def _commercial_chain(session: Session) -> tuple[Customer, Fleet, FleetGroup, Vehicle]:
    customer = Customer(code="C-1", name="Acme", customer_type=CustomerType.COMPANY)
    session.add(customer)
    session.flush()
    fleet = Fleet(customer_id=customer.id, code="KONYA", name="Konya Fleet")
    session.add(fleet)
    session.flush()
    group = FleetGroup(fleet_id=fleet.id, code="HV", name="Heavy Vehicles")
    session.add(group)
    session.flush()
    vehicle = Vehicle(fleet_group_id=group.id, plate="42ABC42")
    session.add(vehicle)
    session.flush()
    return customer, fleet, group, vehicle


def _station_equipment(session: Session) -> tuple[Station, FuelType, Tank, Pump, Nozzle]:
    station = Station(code="S-1", name="Station", city="Konya", district="Selcuklu", address="A")
    fuel_type = FuelType(name="Diesel", code="DSL")
    session.add_all([station, fuel_type])
    session.flush()
    tank = Tank(
        station_id=station.id,
        fuel_type_id=fuel_type.id,
        code="T-1",
        capacity_liters=Decimal("1000"),
        current_level_liters=Decimal("500"),
        minimum_safe_level=Decimal("100"),
        critical_level=Decimal("50"),
    )
    session.add(tank)
    session.flush()
    pump = Pump(
        station_id=station.id,
        tank_id=tank.id,
        code="P-1",
        status=PumpStatus.IDLE,
        nominal_flow_rate=Decimal("10"),
        minimum_flow_rate=Decimal("1"),
        maximum_motor_current=Decimal("10"),
        maximum_pressure=Decimal("10"),
    )
    session.add(pump)
    session.flush()
    nozzle = Nozzle(pump_id=pump.id, fuel_type_id=fuel_type.id, code="N-1", nozzle_number=1)
    session.add(nozzle)
    session.flush()
    return station, fuel_type, tank, pump, nozzle


@pytest.mark.parametrize("customer_type", [CustomerType.COMPANY, CustomerType.INDIVIDUAL])
def test_customer_types_and_authorized_people_are_persisted(
    commercial_session: Session, customer_type: CustomerType
) -> None:
    customer = Customer(code=f"C-{customer_type.value}", name="Acme", customer_type=customer_type)
    commercial_session.add(customer)
    commercial_session.flush()
    commercial_session.add_all(
        [
            CustomerAuthorizedPerson(customer_id=customer.id, full_name="First"),
            CustomerAuthorizedPerson(customer_id=customer.id, full_name="Second"),
        ]
    )
    commercial_session.commit()

    assert customer.customer_type is customer_type
    assert len(customer.authorized_persons) == 2


@pytest.mark.parametrize("discount", [Decimal("-0.01"), Decimal("100.01")])
def test_customer_discount_range_is_enforced(commercial_session: Session, discount: Decimal) -> None:
    commercial_session.add(Customer(code="C-1", name="Acme", customer_type=CustomerType.COMPANY, discount_rate=discount))

    with pytest.raises(IntegrityError):
        commercial_session.commit()


def test_customer_code_and_scoped_fleet_group_codes_are_unique(commercial_session: Session) -> None:
    customer, fleet, group, _ = _commercial_chain(commercial_session)
    commercial_session.commit()
    commercial_session.add(Customer(code=customer.code, name="Duplicate", customer_type=CustomerType.INDIVIDUAL))

    with pytest.raises(IntegrityError):
        commercial_session.commit()
    commercial_session.rollback()

    commercial_session.add(Fleet(customer_id=customer.id, code=fleet.code, name="Duplicate"))
    with pytest.raises(IntegrityError):
        commercial_session.commit()
    commercial_session.rollback()

    other = Customer(code="C-2", name="Other", customer_type=CustomerType.COMPANY)
    commercial_session.add(other)
    commercial_session.flush()
    commercial_session.add(Fleet(customer_id=other.id, code=fleet.code, name="Allowed"))
    commercial_session.commit()

    commercial_session.add(FleetGroup(fleet_id=fleet.id, code=group.code, name="Duplicate"))
    with pytest.raises(IntegrityError):
        commercial_session.commit()


def test_vehicle_and_driver_assignment_constraints(commercial_session: Session) -> None:
    _, _, _, vehicle = _commercial_chain(commercial_session)
    commercial_session.commit()
    commercial_session.add(Vehicle(fleet_group_id=vehicle.fleet_group_id, plate=vehicle.plate))
    with pytest.raises(IntegrityError):
        commercial_session.commit()
    commercial_session.rollback()

    driver = Driver(full_name="Driver", reference_code="D-1")
    commercial_session.add(driver)
    commercial_session.flush()
    assignment = DriverVehicleAssignment(
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        assigned_from=date(2026, 1, 2),
        status=DriverAssignmentStatus.ACTIVE,
    )
    commercial_session.add(assignment)
    commercial_session.commit()
    assert vehicle.driver_assignments == [assignment]

    commercial_session.add(DriverVehicleAssignment(driver_id=driver.id, vehicle_id=vehicle.id, assigned_from=date(2026, 2, 1), assigned_until=date(2026, 1, 31)))
    with pytest.raises(IntegrityError):
        commercial_session.commit()


def test_fuel_card_identity_dates_and_balances_are_constrained(commercial_session: Session) -> None:
    _, _, _, vehicle = _commercial_chain(commercial_session)
    card = FuelCard(vehicle_id=vehicle.id, card_code="CARD-1", display_name="Truck", unit_id="UNIT-1", valid_from=date(2026, 1, 1), payment_type=PaymentType.PREPAID)
    commercial_session.add(card)
    commercial_session.commit()
    assert vehicle.fuel_cards == [card]

    for values in (
        {"card_code": "CARD-1", "unit_id": "UNIT-2"},
        {"card_code": "CARD-2", "unit_id": "UNIT-1"},
        {"card_code": "CARD-3", "unit_id": "UNIT-3", "valid_until": date(2025, 12, 31)},
        {"card_code": "CARD-4", "unit_id": "UNIT-4", "prepaid_balance": Decimal("-1")},
        {"card_code": "CARD-5", "unit_id": "UNIT-5", "credit_limit": Decimal("-1")},
    ):
        commercial_session.add(FuelCard(vehicle_id=vehicle.id, display_name="Invalid", valid_from=date(2026, 1, 1), payment_type=PaymentType.CREDIT, **values))
        with pytest.raises(IntegrityError):
            commercial_session.commit()
        commercial_session.rollback()


@pytest.mark.parametrize("limit_type", list(CardLimitType))
def test_card_limit_types_and_positive_quantity(commercial_session: Session, limit_type: CardLimitType) -> None:
    _, _, _, vehicle = _commercial_chain(commercial_session)
    card = FuelCard(vehicle_id=vehicle.id, card_code="CARD-1", display_name="Truck", unit_id="UNIT-1", valid_from=date(2026, 1, 1), payment_type=PaymentType.PREPAID)
    commercial_session.add(card)
    commercial_session.flush()
    commercial_session.add(FuelCardLimit(fuel_card_id=card.id, limit_type=limit_type, quantity_limit_liters=Decimal("200")))
    commercial_session.commit()

    commercial_session.add(FuelCardLimit(fuel_card_id=card.id, limit_type=limit_type, quantity_limit_liters=Decimal("0")))
    with pytest.raises(IntegrityError):
        commercial_session.commit()


def test_card_permissions_usage_window_and_price_constraints(commercial_session: Session) -> None:
    _, _, _, vehicle = _commercial_chain(commercial_session)
    station, fuel_type, _, _, _ = _station_equipment(commercial_session)
    card = FuelCard(vehicle_id=vehicle.id, card_code="CARD-1", display_name="Truck", unit_id="UNIT-1", valid_from=date(2026, 1, 1), payment_type=PaymentType.PREPAID)
    commercial_session.add(card)
    commercial_session.flush()
    commercial_session.add_all([
        FuelCardAllowedStation(fuel_card_id=card.id, station_id=station.id),
        FuelCardAllowedFuelType(fuel_card_id=card.id, fuel_type_id=fuel_type.id),
        FuelCardUsageWindow(fuel_card_id=card.id, day_of_week=0, start_time=time(6), end_time=time(23)),
        FuelPrice(station_id=station.id, fuel_type_id=fuel_type.id, unit_price=Decimal("42.5"), effective_from=utc_now()),
    ])
    commercial_session.commit()

    commercial_session.add(FuelCardAllowedStation(fuel_card_id=card.id, station_id=station.id))
    with pytest.raises(IntegrityError):
        commercial_session.commit()
    commercial_session.rollback()
    commercial_session.add(FuelCardAllowedFuelType(fuel_card_id=card.id, fuel_type_id=fuel_type.id))
    with pytest.raises(IntegrityError):
        commercial_session.commit()
    commercial_session.rollback()
    commercial_session.add(FuelPrice(station_id=station.id, fuel_type_id=fuel_type.id, unit_price=Decimal("0"), effective_from=utc_now()))
    with pytest.raises(IntegrityError):
        commercial_session.commit()


def test_sale_accepts_legacy_and_commercial_snapshots(commercial_session: Session) -> None:
    customer, fleet, group, vehicle = _commercial_chain(commercial_session)
    station, fuel_type, tank, pump, nozzle = _station_equipment(commercial_session)
    driver = Driver(full_name="Driver")
    card = FuelCard(vehicle_id=vehicle.id, card_code="CARD-1", display_name="Truck", unit_id="UNIT-1", valid_from=date(2026, 1, 1), payment_type=PaymentType.PREPAID)
    commercial_session.add_all([driver, card])
    commercial_session.flush()
    values = dict(station_id=station.id, tank_id=tank.id, pump_id=pump.id, fuel_type_id=fuel_type.id, sale_timestamp=utc_now(), quantity_liters=Decimal("10"), unit_price=Decimal("42"), total_amount=Decimal("420"), duration_seconds=10, level_before=Decimal("500"), level_after=Decimal("490"))
    legacy_sale = Sale(**values)
    commercial_session.add(legacy_sale)
    commercial_session.flush()
    assert legacy_sale.customer_id is None
    commercial_session.add(Sale(**values, customer_id=customer.id, fleet_id=fleet.id, fleet_group_id=group.id, vehicle_id=vehicle.id, driver_id=driver.id, fuel_card_id=card.id, nozzle_id=nozzle.id, start_totalizer_liters=Decimal("100"), end_totalizer_liters=Decimal("110"), list_unit_price=Decimal("45"), discount_rate=Decimal("5"), sale_status=SaleStatus.COMPLETED))
    commercial_session.commit()

    commercial_session.add(Sale(**values, start_totalizer_liters=Decimal("-1")))
    with pytest.raises(IntegrityError):
        commercial_session.commit()
    commercial_session.rollback()
    commercial_session.add(Sale(**values, start_totalizer_liters=Decimal("11"), end_totalizer_liters=Decimal("10")))
    with pytest.raises(IntegrityError):
        commercial_session.commit()
    commercial_session.rollback()
    commercial_session.add(
        Sale(
            **values,
            start_totalizer_liters=Decimal("100"),
            end_totalizer_liters=Decimal("111"),
        )
    )
    with pytest.raises(IntegrityError):
        commercial_session.commit()
