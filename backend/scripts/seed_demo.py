"""Idempotently seed canonical simulation equipment for station KONYA_TEST."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.exceptions import BusinessRuleError, NotFoundError
from app.repositories.fuel_type_repository import FuelTypeRepository
from app.repositories.pump_repository import PumpRepository
from app.repositories.station_repository import StationRepository
from app.repositories.tank_repository import TankRepository
from app.utils.enums import PumpStatus, SensorStatus

_DEMO_STATION_ID = 2
_DEMO_STATION_CODE = "KONYA_TEST"
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


def seed_konya_simulation_demo(db: Session) -> dict[str, int]:
    """Seed station 2's canonical fuels, three tanks, and six pumps atomically.

    The function intentionally never reads, updates, or removes Station 1 audit/test
    records. Re-running it uses canonical codes and station-scoped equipment codes.
    """

    station = StationRepository(db).get(_DEMO_STATION_ID)
    if station is None:
        raise NotFoundError("KONYA_TEST station (id=2) was not found.")
    if station.code != _DEMO_STATION_CODE:
        raise BusinessRuleError("Station id=2 is not the KONYA_TEST demo station.")
    if not station.is_active:
        raise BusinessRuleError("KONYA_TEST demo station must be active.")

    fuels = FuelTypeRepository(db)
    tanks = TankRepository(db)
    pumps = PumpRepository(db)
    try:
        fuel_by_code = {
            code: _get_or_create_fuel(fuels, name=name, code=code)
            for name, code in _FUELS
        }
        tank_by_code = {
            code: _get_or_create_tank(
                tanks,
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
                    code=f"PUMP_{fuel_code}_{suffix}",
                    tank_id=tank_by_code[tank_code].id,
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"fuel_types": len(fuel_by_code), "tanks": len(tank_by_code), "pumps": 6}


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
    code: str,
    fuel_type_id: int,
    capacity: str,
    current_level: str,
):
    tank = repository.get_by_station_and_code(_DEMO_STATION_ID, code)
    if tank is not None:
        if tank.fuel_type_id != fuel_type_id:
            raise BusinessRuleError(f"Demo tank {code} has an incompatible fuel type.")
        return tank
    capacity_value = Decimal(capacity)
    return repository.create(
        {
            "station_id": _DEMO_STATION_ID,
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


def _get_or_create_pump(repository: PumpRepository, *, code: str, tank_id: int):
    pump = repository.get_by_station_and_code(_DEMO_STATION_ID, code)
    if pump is not None:
        if pump.tank_id != tank_id:
            raise BusinessRuleError(f"Demo pump {code} has an incompatible tank.")
        return pump
    return repository.create(
        {
            "station_id": _DEMO_STATION_ID,
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


def main() -> None:
    """Run the KONYA_TEST demo seed against the configured database."""

    with SessionLocal() as db:
        summary = seed_konya_simulation_demo(db)
    print(f"Seeded KONYA_TEST demo: {summary}")


if __name__ == "__main__":
    main()
