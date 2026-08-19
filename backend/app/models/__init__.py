"""Import all models so Alembic can discover complete metadata."""

from app.models.alarm import Alarm
from app.models.audit_log import AuditLog
from app.models.communication_port import CommunicationPort
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
from app.models.delivery import Delivery
from app.models.device_controller import DeviceController
from app.models.fuel_type import FuelType
from app.models.forecast import Forecast
from app.models.fault import Fault
from app.models.model_version import ModelVersion
from app.models.order_recommendation import OrderRecommendation
from app.models.nozzle import Nozzle
from app.models.operations import Attendant, AttendantShiftAssignment, Shift
from app.models.pump import Pump
from app.models.probe_reading import ProbeReading
from app.models.sale import Sale
from app.models.sensor_reading import SensorReading
from app.models.simulation_scenario import SimulationScenario
from app.models.simulation_event import SimulationEvent
from app.models.simulation_run import SimulationRun
from app.models.station import Station
from app.models.tank import Tank
from app.models.tank_probe import TankProbe
from app.models.user import User

__all__ = [
    "Alarm",
    "AuditLog",
    "Attendant", "AttendantShiftAssignment",
    "CommunicationPort",
    "Customer",
    "CustomerAuthorizedPerson",
    "Delivery",
    "DeviceController",
    "Driver",
    "DriverVehicleAssignment",
    "Fleet",
    "FleetGroup",
    "Fault",
    "FuelCard",
    "FuelCardAllowedFuelType",
    "FuelCardAllowedStation",
    "FuelCardLimit",
    "FuelCardUsageWindow",
    "FuelPrice",
    "FuelType",
    "Forecast",
    "ModelVersion",
    "OrderRecommendation",
    "Nozzle",
    "Pump",
    "ProbeReading",
    "Sale",
    "SensorReading",
    "Shift",
    "SimulationScenario",
    "SimulationEvent",
    "SimulationRun",
    "Station",
    "Tank",
    "TankProbe",
    "User",
    "Vehicle",
]
