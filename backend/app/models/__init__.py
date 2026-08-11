"""Import all models so Alembic can discover complete metadata."""

from app.models.alarm import Alarm
from app.models.delivery import Delivery
from app.models.fuel_type import FuelType
from app.models.forecast import Forecast
from app.models.model_version import ModelVersion
from app.models.order_recommendation import OrderRecommendation
from app.models.pump import Pump
from app.models.sale import Sale
from app.models.sensor_reading import SensorReading
from app.models.simulation_scenario import SimulationScenario
from app.models.simulation_event import SimulationEvent
from app.models.simulation_run import SimulationRun
from app.models.station import Station
from app.models.tank import Tank
from app.models.user import User

__all__ = [
    "Alarm",
    "Delivery",
    "FuelType",
    "Forecast",
    "ModelVersion",
    "OrderRecommendation",
    "Pump",
    "Sale",
    "SensorReading",
    "SimulationScenario",
    "SimulationEvent",
    "SimulationRun",
    "Station",
    "Tank",
    "User",
]
