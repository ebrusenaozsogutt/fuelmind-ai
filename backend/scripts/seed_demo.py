"""Idempotently seed canonical simulation equipment for station KONYA_TEST."""

from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.seed import seed_demo_users
from app.exceptions import BusinessRuleError
from app.repositories.fuel_type_repository import FuelTypeRepository
from app.repositories.communication_port_repository import CommunicationPortRepository
from app.repositories.device_controller_repository import DeviceControllerRepository
from app.repositories.nozzle_repository import NozzleRepository
from app.repositories.pump_repository import PumpRepository
from app.repositories.station_repository import StationRepository
from app.repositories.tank_repository import TankRepository
from app.repositories.tank_probe_repository import TankProbeRepository
from app.models.commercial import (
    Customer,
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
from app.models.delivery import Delivery
from app.models.nozzle import Nozzle
from app.models.pump import Pump
from app.models.sale import Sale
from app.schemas.delivery import DeliveryCreate
from app.schemas.sale import CommercialSaleRequest
from app.services.commercial_sale_service import CommercialSaleService
from app.services.delivery_service import DeliveryService
from app.services.forecast_generation_service import ForecastGenerationService
from app.models.operations import Attendant, AttendantShiftAssignment, Shift
from app.utils.enums import (
    ControllerStatus,
    ControllerType,
    NozzleStatus,
    PortStatus,
    PortType,
    ProbeStatus,
    PumpStatus,
    CardStatus,
    CardLimitType,
    CustomerType,
    DriverAssignmentStatus,
    PaymentType,
    SensorStatus,
)
from app.utils.datetime_utils import utc_now

_DEMO_STATION_CODE = "KONYA_TEST"
_DEMO_CONTROLLER_CODE = "USC-01"
_FUELS = (
    ("Motorin", "DIESEL"),
    ("Benzin", "GASOLINE"),
    ("LPG", "LPG"),
)
_TANKS = (
    ("TANK_DIESEL_01", "DIESEL", "30000", "21000"),
    ("TANK_GASOLINE_01", "GASOLINE", "25000", "17500"),
    ("TANK_LPG_01", "LPG", "20000", "14000"),
)
_ATTENDANTS = (
    ("ATT-01", "Ayşe Demir", "KONYA-ATT-001"),
    ("ATT-02", "Mehmet Kaya", "KONYA-ATT-002"),
    ("ATT-03", "Elif Şahin", "KONYA-ATT-003"),
    ("ATT-04", "Burak Yıldız", "KONYA-ATT-004"),
    ("ATT-05", "Zeynep Arslan", "KONYA-ATT-005"),
    ("ATT-06", "Can Koç", "KONYA-ATT-006"),
)
_SHIFTS = (
    ("SABAH", "Sabah", time(8), time(16)),
    ("AKSAM", "Akşam", time(16), time(0)),
    ("GECE", "Gece", time(0), time(8)),
)


def seed_konya_simulation_demo(db: Session) -> dict[str, int]:
    """Seed KONYA_TEST's canonical equipment and minimal field topology atomically.

    The function intentionally never reads, updates, or removes Station 1 audit/test
    records. Re-running it uses canonical codes and station-scoped equipment codes.
    """

    station = StationRepository(db).get_by_code(_DEMO_STATION_CODE)
    if station is None:
        station = StationRepository(db).create(
            {
                "code": _DEMO_STATION_CODE,
                "name": "Konya Test İstasyonu",
                "city": "Konya",
                "district": "Selçuklu",
                "address": "Yerel demo istasyonu",
                "is_active": True,
            }
        )
    if not station.is_active:
        raise BusinessRuleError("KONYA_TEST demo station must be active.")

    fuels = FuelTypeRepository(db)
    tanks = TankRepository(db)
    pumps = PumpRepository(db)
    controllers = DeviceControllerRepository(db)
    ports = CommunicationPortRepository(db)
    probes = TankProbeRepository(db)
    nozzles = NozzleRepository(db)
    try:
        fuel_by_code = {
            code: _get_or_create_fuel(fuels, name=name, code=code)
            for name, code in _FUELS
        }
        tank_by_code = {
            code: _get_or_create_tank(
                tanks,
                station_id=station.id,
                code=code,
                fuel_type_id=fuel_by_code[fuel_code].id,
                capacity=capacity,
                current_level=current_level,
            )
            for code, fuel_code, capacity, current_level in _TANKS
        }
        for tank_code, fuel_code, _, _ in _TANKS:
            for suffix in ("01", "02"):
                _get_or_create_pump(
                    pumps,
                    station_id=station.id,
                    code=f"PUMP_{fuel_code}_{suffix}",
                    tank_id=tank_by_code[tank_code].id,
                )
        _seed_topology(
            station_id=station.id,
            tank_by_code=tank_by_code,
            controllers=controllers,
            ports=ports,
            pumps=pumps,
            probes=probes,
            nozzles=nozzles,
        )
        if hasattr(db, "scalar"):
            _seed_commercial_demo(db, station.id, fuel_by_code)
            _seed_operations_demo(db, station.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "fuel_types": len(fuel_by_code),
        "tanks": len(tank_by_code),
        "pumps": 6,
        "controllers": 1,
        "ports": 3,
        "probes": len(tank_by_code),
        "nozzles": 6,
        "attendants": len(_ATTENDANTS),
        "shifts": len(_SHIFTS),
        "attendant_shift_assignments": len(_ATTENDANTS),
    }


def _seed_operations_demo(db: Session, station_id: int) -> None:
    """Create idempotent attendants, three shifts, and active shift assignments."""

    attendants = {
        code: _get_or_create_demo_attendant(
            db,
            station_id=station_id,
            code=code,
            full_name=full_name,
            employee_number=employee_number,
        )
        for code, full_name, employee_number in _ATTENDANTS
    }
    shifts = {
        code: _get_or_create_demo_shift(
            db,
            station_id=station_id,
            code=code,
            name=name,
            start_time=start_time,
            end_time=end_time,
        )
        for code, name, start_time, end_time in _SHIFTS
    }
    ordered_shifts = tuple(shifts.values())
    for index, attendant in enumerate(attendants.values()):
        shift = ordered_shifts[index % len(ordered_shifts)]
        assignment = db.scalar(
            select(AttendantShiftAssignment).where(
                AttendantShiftAssignment.attendant_id == attendant.id,
                AttendantShiftAssignment.shift_id == shift.id,
            )
        )
        if assignment is None:
            db.add(
                AttendantShiftAssignment(
                    attendant_id=attendant.id,
                    shift_id=shift.id,
                    station_id=station_id,
                    is_active=True,
                )
            )
        else:
            assignment.station_id = station_id
            assignment.is_active = True


def _get_or_create_demo_attendant(
    db: Session,
    *,
    station_id: int,
    code: str,
    full_name: str,
    employee_number: str,
) -> Attendant:
    attendant = db.scalar(
        select(Attendant).where(
            Attendant.station_id == station_id,
            Attendant.code == code,
        )
    )
    if attendant is None:
        attendant = Attendant(
            station_id=station_id,
            code=code,
            full_name=full_name,
            employee_number=employee_number,
            is_active=True,
        )
        db.add(attendant)
        db.flush()
    else:
        attendant.full_name = full_name
        attendant.is_active = True
    return attendant


def _get_or_create_demo_shift(
    db: Session,
    *,
    station_id: int,
    code: str,
    name: str,
    start_time: time,
    end_time: time,
) -> Shift:
    shift = db.scalar(
        select(Shift).where(Shift.station_id == station_id, Shift.code == code)
    )
    if shift is None:
        shift = Shift(
            station_id=station_id,
            code=code,
            name=name,
            start_time=start_time,
            end_time=end_time,
            is_active=True,
        )
        db.add(shift)
        db.flush()
    else:
        shift.name = name
        shift.is_active = True
    return shift


def _seed_commercial_demo(db: Session, station_id: int, fuel_by_code: dict[str, object]) -> None:
    """Create two idempotent card-backed demo vehicles for Prompt 7 acceptance."""

    customer = db.scalar(select(Customer).where(Customer.code == "KONYA-LOJISTIK-DEMO"))
    if customer is None:
        customer = Customer(
            code="KONYA-LOJISTIK-DEMO",
            name="KONYA LOJISTIK DEMO",
            customer_type=CustomerType.COMPANY,
            discount_rate=Decimal("3"),
        )
        db.add(customer)
        db.flush()
    fleet = db.scalar(
        select(Fleet).where(Fleet.customer_id == customer.id, Fleet.code == "KONYA")
    )
    if fleet is None:
        fleet = Fleet(customer_id=customer.id, code="KONYA", name="Konya Filosu")
        db.add(fleet)
        db.flush()
    group = db.scalar(
        select(FleetGroup).where(FleetGroup.fleet_id == fleet.id, FleetGroup.code == "AGIR")
    )
    if group is None:
        group = FleetGroup(fleet_id=fleet.id, code="AGIR", name="Ağır Vasıta")
        db.add(group)
        db.flush()
    driver = _get_or_create_demo_driver(db, "DEMO-SOFOR", "Demo Şoför")
    credit_driver = _get_or_create_demo_driver(db, "DEMO-SOFOR-2", "Demo Şoför 2")
    prepaid_vehicle = _get_or_create_demo_vehicle(db, group.id, "42 DEMO 01")
    _get_or_create_demo_vehicle(db, group.id, "42 DEMO 02")  # intentionally cardless acceptance vehicle
    credit_vehicle = _get_or_create_demo_vehicle(db, group.id, "42 DEMO 03")
    lpg_vehicle = _get_or_create_demo_vehicle(db, group.id, "42 DEMO 04")
    _get_or_create_assignment(db, driver.id, prepaid_vehicle.id)
    _get_or_create_assignment(db, credit_driver.id, credit_vehicle.id)
    prepaid = _get_or_create_demo_card(
        db,
        prepaid_vehicle.id,
        "DEMO-CARD-01",
        "UNIT-DEMO-001",
        PaymentType.PREPAID,
    )
    credit = _get_or_create_demo_card(
        db,
        credit_vehicle.id,
        "DEMO-CARD-02",
        "UNIT-DEMO-002",
        PaymentType.CREDIT,
    )
    lpg = _get_or_create_demo_card(
        db,
        lpg_vehicle.id,
        "DEMO-CARD-03",
        "UNIT-DEMO-003",
        PaymentType.PREPAID,
    )
    # Move an older idempotent seed's CREDIT demo card away from the acceptance vehicle.
    if credit.vehicle_id != credit_vehicle.id:
        credit.vehicle_id = credit_vehicle.id
    _restore_demo_commercial_state(
        customer, fleet, group, prepaid_vehicle, credit_vehicle, prepaid, credit
    )
    lpg_vehicle.is_active = True
    lpg.status = CardStatus.ACTIVE
    lpg.is_active = True
    lpg.valid_from = date(2020, 1, 1)
    lpg.valid_until = None
    lpg.prepaid_balance = max(Decimal(lpg.prepaid_balance), Decimal("100000"))
    lpg.credit_limit = Decimal("0")
    lpg.credit_used = Decimal("0")
    for card in (prepaid, credit, lpg):
        if db.scalar(
            select(FuelCardAllowedStation.id).where(
                FuelCardAllowedStation.fuel_card_id == card.id,
                FuelCardAllowedStation.station_id == station_id,
            )
        ) is None:
            db.add(FuelCardAllowedStation(fuel_card_id=card.id, station_id=station_id))
        for fuel in fuel_by_code.values():
            if db.scalar(
                select(FuelCardAllowedFuelType.id).where(
                    FuelCardAllowedFuelType.fuel_card_id == card.id,
                    FuelCardAllowedFuelType.fuel_type_id == fuel.id,
                )
            ) is None:
                db.add(FuelCardAllowedFuelType(fuel_card_id=card.id, fuel_type_id=fuel.id))
        _ensure_demo_card_limits(db, card)
        _ensure_demo_card_usage_windows(db, card)
    for fuel in fuel_by_code.values():
        _ensure_current_demo_price(db, station_id, fuel.id)


def _restore_demo_commercial_state(customer, fleet, group, prepaid_vehicle, credit_vehicle, prepaid, credit) -> None:
    """Make repeated seed runs a usable runtime fixture, not merely duplicate-free."""

    for entity in (customer, fleet, group, prepaid_vehicle, credit_vehicle):
        entity.is_active = True
    for card, payment_type in ((prepaid, PaymentType.PREPAID), (credit, PaymentType.CREDIT)):
        card.status = CardStatus.ACTIVE
        card.is_active = True
        card.valid_from = date(2020, 1, 1)
        card.valid_until = None
        card.payment_type = payment_type
        if payment_type == PaymentType.PREPAID:
            card.prepaid_balance = max(Decimal(card.prepaid_balance), Decimal("100000"))
            card.credit_limit = Decimal("0")
            card.credit_used = Decimal("0")
        else:
            card.prepaid_balance = Decimal("0")
            card.credit_limit = max(Decimal(card.credit_limit), Decimal("100000"))
            card.credit_used = Decimal("0")


def _ensure_current_demo_price(db: Session, station_id: int, fuel_type_id: int) -> None:
    now = utc_now()
    prices = list(db.scalars(select(FuelPrice).where(
        FuelPrice.station_id == station_id,
        FuelPrice.fuel_type_id == fuel_type_id,
        FuelPrice.is_active.is_(True),
    )))
    has_current = any(
        price.effective_from <= now
        and (price.effective_until is None or price.effective_until > now)
        for price in prices
    )
    if not any(price.effective_from <= now - timedelta(days=30) for price in prices):
        db.add(FuelPrice(
            station_id=station_id,
            fuel_type_id=fuel_type_id,
            unit_price=Decimal("50"),
            effective_from=now - timedelta(days=365),
            effective_until=now - timedelta(days=30),
            is_active=True,
        ))
    if not has_current:
        future_starts = [price.effective_from for price in prices if price.effective_from > now]
        db.add(FuelPrice(
            station_id=station_id,
            fuel_type_id=fuel_type_id,
            unit_price=Decimal("55"),
            effective_from=now,
            effective_until=min(future_starts) if future_starts else None,
            is_active=True,
        ))


def _ensure_demo_card_limits(db: Session, card: FuelCard) -> None:
    """Give each active local card visible, non-blocking authorization limits."""

    limits = (
        (CardLimitType.PER_TRANSACTION, Decimal("100000")),
        (CardLimitType.DAILY, Decimal("100000")),
        (CardLimitType.MONTHLY, Decimal("100000")),
    )
    for limit_type, quantity in limits:
        limit = db.scalar(
            select(FuelCardLimit).where(
                FuelCardLimit.fuel_card_id == card.id,
                FuelCardLimit.limit_type == limit_type,
                FuelCardLimit.is_active.is_(True),
            )
        )
        if limit is None:
            db.add(
                FuelCardLimit(
                    fuel_card_id=card.id,
                    limit_type=limit_type,
                    quantity_limit_liters=quantity,
                    valid_from=date(2020, 1, 1),
                    valid_until=None,
                    is_active=True,
                )
            )
        else:
            limit.quantity_limit_liters = max(
                Decimal(limit.quantity_limit_liters), quantity
            )
            limit.valid_from = date(2020, 1, 1)
            limit.valid_until = None


def _ensure_demo_card_usage_windows(db: Session, card: FuelCard) -> None:
    """Keep historical demo sales authorized on every weekday and at every hour."""

    for day_of_week in range(7):
        exists = db.scalar(
            select(FuelCardUsageWindow.id).where(
                FuelCardUsageWindow.fuel_card_id == card.id,
                FuelCardUsageWindow.day_of_week == day_of_week,
                FuelCardUsageWindow.start_time == time(0, 0),
                FuelCardUsageWindow.end_time == time(23, 59),
                FuelCardUsageWindow.is_active.is_(True),
            )
        )
        if exists is None:
            db.add(
                FuelCardUsageWindow(
                    fuel_card_id=card.id,
                    day_of_week=day_of_week,
                    start_time=time(0, 0),
                    end_time=time(23, 59),
                    is_active=True,
                )
            )


def _get_or_create_demo_vehicle(db: Session, group_id: int, plate: str) -> Vehicle:
    vehicle = db.scalar(select(Vehicle).where(Vehicle.plate == plate))
    if vehicle is None:
        vehicle = Vehicle(fleet_group_id=group_id, plate=plate)
        db.add(vehicle)
        db.flush()
    return vehicle


def _get_or_create_demo_driver(db: Session, reference_code: str, full_name: str) -> Driver:
    driver = db.scalar(select(Driver).where(Driver.reference_code == reference_code))
    if driver is None:
        driver = Driver(full_name=full_name, reference_code=reference_code)
        db.add(driver)
        db.flush()
    driver.is_active = True
    return driver


def _get_or_create_assignment(db: Session, driver_id: int, vehicle_id: int) -> None:
    assignment = db.scalar(
        select(DriverVehicleAssignment).where(
            DriverVehicleAssignment.driver_id == driver_id,
            DriverVehicleAssignment.vehicle_id == vehicle_id,
            DriverVehicleAssignment.status == DriverAssignmentStatus.ACTIVE,
        )
    )
    if assignment is None:
        db.add(
            DriverVehicleAssignment(
                driver_id=driver_id,
                vehicle_id=vehicle_id,
                assigned_from=date(2020, 1, 1),
                status=DriverAssignmentStatus.ACTIVE,
            )
        )


def _get_or_create_demo_card(
    db: Session,
    vehicle_id: int,
    card_code: str,
    unit_id: str,
    payment_type: PaymentType,
) -> FuelCard:
    card = db.scalar(select(FuelCard).where(FuelCard.card_code == card_code))
    if card is None:
        card = FuelCard(
            vehicle_id=vehicle_id,
            card_code=card_code,
            display_name=card_code,
            unit_id=unit_id,
            status=CardStatus.ACTIVE,
            valid_from=date(2020, 1, 1),
            payment_type=payment_type,
            prepaid_balance=Decimal("100000") if payment_type == PaymentType.PREPAID else Decimal("0"),
            credit_limit=Decimal("100000") if payment_type == PaymentType.CREDIT else Decimal("0"),
            credit_used=Decimal("0"),
            is_active=True,
        )
        db.add(card)
        db.flush()
    return card


def _get_or_create_fuel(
    repository: FuelTypeRepository, *, name: str, code: str
):
    fuel = repository.get_by_code(code)
    if fuel is not None:
        return fuel
    return repository.create(
        {"name": name, "code": code, "unit": "LITER", "is_active": True}
    )


def _get_or_create_tank(
    repository: TankRepository,
    *,
    station_id: int,
    code: str,
    fuel_type_id: int,
    capacity: str,
    current_level: str,
):
    tank = repository.get_by_station_and_code(station_id, code)
    if tank is not None:
        if tank.fuel_type_id != fuel_type_id:
            raise BusinessRuleError(f"Demo tank {code} has an incompatible fuel type.")
        return tank
    capacity_value = Decimal(capacity)
    return repository.create(
        {
            "station_id": station_id,
            "fuel_type_id": fuel_type_id,
            "code": code,
            "capacity_liters": capacity_value,
            "current_level_liters": Decimal(current_level),
            "minimum_safe_level": capacity_value * Decimal("0.25"),
            "critical_level": capacity_value * Decimal("0.15"),
            "water_level": Decimal("0"),
            "temperature": Decimal("20"),
            "sensor_status": SensorStatus.ACTIVE,
            "is_active": True,
        }
    )


def _get_or_create_pump(
    repository: PumpRepository, *, station_id: int, code: str, tank_id: int
):
    pump = repository.get_by_station_and_code(station_id, code)
    if pump is not None:
        if pump.tank_id != tank_id:
            raise BusinessRuleError(f"Demo pump {code} has an incompatible tank.")
        return pump
    return repository.create(
        {
            "station_id": station_id,
            "tank_id": tank_id,
            "code": code,
            "status": PumpStatus.IDLE,
            "nominal_flow_rate": Decimal("45"),
            "minimum_flow_rate": Decimal("10"),
            "maximum_motor_current": Decimal("18"),
            "maximum_pressure": Decimal("8"),
            "total_working_hours": Decimal("0"),
            "is_active": True,
        }
    )


def _seed_topology(
    *,
    station_id: int,
    tank_by_code: dict[str, object],
    controllers: DeviceControllerRepository,
    ports: CommunicationPortRepository,
    pumps: PumpRepository,
    probes: TankProbeRepository,
    nozzles: NozzleRepository,
) -> None:
    """Attach existing canonical equipment to an intentionally small demo topology."""

    controller = controllers.get_by_station_and_code(station_id, _DEMO_CONTROLLER_CODE)
    if controller is None:
        controller = controllers.create(
            {
                "station_id": station_id,
                "code": _DEMO_CONTROLLER_CODE,
                "name": "KONYA Test Forecourt Controller",
                "controller_type": ControllerType.USC,
                "status": ControllerStatus.ONLINE,
                "is_active": True,
            }
        )
    port_by_number = {
        number: _get_or_create_port(ports, controller_id=controller.id, number=number, port_type=port_type)
        for number, port_type in ((1, PortType.PUMP), (2, PortType.PUMP), (3, PortType.PROBE))
    }

    ordered_pumps = [
        pumps.get_by_station_and_code(station_id, f"PUMP_{fuel_code}_{suffix}")
        for _, fuel_code, _, _ in _TANKS
        for suffix in ("01", "02")
    ]
    for index, pump in enumerate(pump for pump in ordered_pumps if pump is not None):
        if pump.communication_port_id is None:
            pump.communication_port_id = port_by_number[1 if index % 2 == 0 else 2].id
        if nozzles.get_by_pump_and_number(pump.id, 1) is None:
            tank = next(tank for tank in tank_by_code.values() if tank.id == pump.tank_id)
            nozzles.create(
                {
                    "pump_id": pump.id,
                    "fuel_type_id": tank.fuel_type_id,
                    "code": f"NOZZLE_{pump.code}",
                    "nozzle_number": 1,
                    "status": NozzleStatus.AVAILABLE,
                    "totalizer_liters": Decimal("100000") + Decimal(index * 1000),
                    "is_active": True,
                }
            )

    for tank in tank_by_code.values():
        if probes.get_active_by_tank(tank.id) is None:
            probes.create(
                {
                    "tank_id": tank.id,
                    "communication_port_id": port_by_number[3].id,
                    "code": f"PROBE_{tank.code}",
                    "name": f"{tank.code} Probe",
                    "status": ProbeStatus.ONLINE,
                    "is_active": True,
                }
            )


def _get_or_create_port(
    repository: CommunicationPortRepository,
    *,
    controller_id: int,
    number: int,
    port_type: PortType,
):
    port = repository.get_by_controller_and_number(controller_id, number)
    if port is not None:
        if port.port_type != port_type:
            raise BusinessRuleError(f"Demo port {number} has an incompatible type.")
        return port
    return repository.create(
        {
            "controller_id": controller_id,
            "port_number": number,
            "name": f"PORT {number}",
            "port_type": port_type,
            "protocol": "RS-485",
            "baud_rate": 9600,
            "status": PortStatus.ONLINE,
            "is_active": True,
        }
    )


def _seed_demo_transactions(db: Session) -> None:
    """Create service-backed historical sales, deliveries, and seven-day forecasts."""

    station = StationRepository(db).get_by_code(_DEMO_STATION_CODE)
    if station is None:
        raise BusinessRuleError("Demo station was not created.")
    now = utc_now().replace(hour=12, minute=0, second=0, microsecond=0)
    cards = {
        "DIESEL": "UNIT-DEMO-001",
        "GASOLINE": "UNIT-DEMO-002",
        "LPG": "UNIT-DEMO-003",
    }
    attendants = list(
        db.scalars(
            select(Attendant).where(Attendant.station_id == station.id).order_by(Attendant.id)
        )
    )
    shifts = list(
        db.scalars(select(Shift).where(Shift.station_id == station.id).order_by(Shift.id))
    )
    for fuel_code, unit_id in cards.items():
        fuel = FuelTypeRepository(db).get_by_code(fuel_code)
        if fuel is None:
            raise BusinessRuleError(f"Demo fuel {fuel_code} was not created.")
        nozzle = db.scalar(
            select(Nozzle)
            .join(Pump, Nozzle.pump_id == Pump.id)
            .where(Pump.station_id == station.id, Nozzle.fuel_type_id == fuel.id)
            .order_by(Nozzle.id)
        )
        if nozzle is None:
            raise BusinessRuleError(f"Demo nozzle for {fuel_code} was not created.")
        tank = nozzle.pump.tank
        delivery_marker = f"DEMO-DELIVERY-{fuel_code}"
        if db.scalar(select(Delivery.id).where(Delivery.simulation_delivery_id == delivery_marker)) is None:
            delivery = DeliveryService(db).create(
                DeliveryCreate(
                    tank_id=tank.id,
                    delivery_timestamp=now - timedelta(days=15),
                    quantity_liters=Decimal("1000"),
                    supplier_name="FuelMind Demo Tedarik",
                )
            )
            delivery.simulation_delivery_id = delivery_marker
            db.commit()
        for day in range(14, 0, -1):
            marker = f"DEMO-SALE-{fuel_code}-{day}"
            if db.scalar(select(Sale.id).where(Sale.simulation_sale_id == marker)) is not None:
                continue
            result = CommercialSaleService(db).complete(
                CommercialSaleRequest(
                    unit_id=unit_id,
                    nozzle_id=nozzle.id,
                    quantity_liters=Decimal("25"),
                    started_at=now - timedelta(days=day),
                )
            )
            if not result.completed or result.sale is None:
                raise BusinessRuleError(f"Demo sale {marker} was rejected: {result.message}")
            sale = db.get(Sale, result.sale.id)
            if sale is None:
                raise BusinessRuleError("Completed demo sale could not be reloaded.")
            sale.simulation_sale_id = marker
            if attendants and shifts:
                index = day % min(len(attendants), len(shifts))
                sale.attendant_id = attendants[index].id
                sale.shift_id = shifts[index].id
            db.commit()
    ForecastGenerationService(db).generate(station.id)


def seed_final_demo(db: Session) -> dict[str, int]:
    """Run the complete local demo fixture after the configured users are enabled."""

    users = seed_demo_users(db)
    summary = seed_konya_simulation_demo(db)
    _seed_demo_transactions(db)
    summary.update({"users_created": len(users), "sales": 42, "deliveries": 3, "forecasts": 21})
    return summary


def main() -> None:
    """Run the complete KONYA_TEST local demo seed against the configured database."""

    with SessionLocal() as db:
        summary = seed_final_demo(db)
    print(f"Seeded KONYA_TEST demo: {summary}")


if __name__ == "__main__":
    main()
