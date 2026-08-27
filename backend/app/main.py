"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.audit_logs import router as audit_logs_router
from app.api.alarms import router as alarms_router
from app.api.communication_ports import router as communication_ports_router
from app.api.customer_authorized_persons import router as customer_authorized_persons_router
from app.api.customers import router as customers_router
from app.api.deliveries import router as deliveries_router
from app.api.dashboard import router as dashboard_router
from app.api.device_controllers import router as device_controllers_router
from app.api.driver_vehicle_assignments import router as driver_vehicle_assignments_router
from app.api.drivers import router as drivers_router
from app.api.error_handlers import register_exception_handlers
from app.api.fuel_types import router as fuel_types_router
from app.api.forecasts import router as forecasts_router
from app.api.faults import router as faults_router
from app.api.fuel_cards import router as fuel_cards_router
from app.api.fuel_prices import router as fuel_prices_router
from app.api.fleet_groups import router as fleet_groups_router
from app.api.fleets import router as fleets_router
from app.api.live import router as live_router
from app.api.models import router as models_router
from app.api.nozzles import router as nozzles_router
from app.api.operations import router as operations_router
from app.api.pumps import router as pumps_router
from app.api.sales import router as sales_router
from app.api.reports import router as reports_router
from app.api.sensor_readings import router as sensor_readings_router
from app.api.simulations import router as simulations_router
from app.api.stations import router as stations_router
from app.api.tanks import router as tanks_router
from app.api.tank_probes import router as tank_probes_router
from app.api.users import router as users_router
from app.api.vehicles import router as vehicles_router
from app.config import settings
from app.live.connection_manager import ConnectionManager
from app.live.event_broker import LiveEventBroker
from app.simulation.manager import SimulationManager
from app.utils.logging import configure_logging
from app.workers.startup_recovery import recover_interrupted_simulation_runs


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Configure application resources when the server starts."""

    configure_logging(settings.LOG_LEVEL)
    logging.getLogger(__name__).info("%s started", settings.APP_NAME)
    recover_interrupted_simulation_runs()
    connection_manager = ConnectionManager()
    application.state.connection_manager = connection_manager
    live_event_broker = LiveEventBroker(connection_manager)
    application.state.live_event_broker = live_event_broker
    manager = SimulationManager(live_event_broker=live_event_broker)
    application.state.simulation_manager = manager
    try:
        yield
    finally:
        await manager.shutdown()
        logging.getLogger(__name__).info("%s stopped", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
register_exception_handlers(app)
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(audit_logs_router, prefix=settings.API_PREFIX)
app.include_router(alarms_router, prefix=settings.API_PREFIX)
app.include_router(communication_ports_router, prefix=settings.API_PREFIX)
app.include_router(customers_router, prefix=settings.API_PREFIX)
app.include_router(customer_authorized_persons_router, prefix=settings.API_PREFIX)
app.include_router(fleets_router, prefix=settings.API_PREFIX)
app.include_router(fleet_groups_router, prefix=settings.API_PREFIX)
app.include_router(vehicles_router, prefix=settings.API_PREFIX)
app.include_router(drivers_router, prefix=settings.API_PREFIX)
app.include_router(driver_vehicle_assignments_router, prefix=settings.API_PREFIX)
app.include_router(fuel_types_router, prefix=settings.API_PREFIX)
app.include_router(forecasts_router, prefix=settings.API_PREFIX)
app.include_router(faults_router, prefix=settings.API_PREFIX)
app.include_router(fuel_cards_router, prefix=settings.API_PREFIX)
app.include_router(fuel_prices_router, prefix=settings.API_PREFIX)
app.include_router(stations_router, prefix=settings.API_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_PREFIX)
app.include_router(device_controllers_router, prefix=settings.API_PREFIX)
app.include_router(tanks_router, prefix=settings.API_PREFIX)
app.include_router(tank_probes_router, prefix=settings.API_PREFIX)
app.include_router(pumps_router, prefix=settings.API_PREFIX)
app.include_router(nozzles_router, prefix=settings.API_PREFIX)
app.include_router(operations_router, prefix=settings.API_PREFIX)
app.include_router(users_router, prefix=settings.API_PREFIX)
app.include_router(sales_router, prefix=settings.API_PREFIX)
app.include_router(reports_router, prefix=settings.API_PREFIX)
app.include_router(sensor_readings_router, prefix=settings.API_PREFIX)
app.include_router(deliveries_router, prefix=settings.API_PREFIX)
app.include_router(simulations_router, prefix=settings.API_PREFIX)
app.include_router(live_router, prefix=settings.API_PREFIX)
app.include_router(models_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["system"])
async def read_root() -> dict[str, str]:
    """Return basic API information."""

    return {"application": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get(f"{settings.API_PREFIX}/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Return the service health and runtime environment."""

    return {
        "status": "ok",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health", tags=["system"])
async def service_health_check() -> dict[str, str]:
    """Return the unprefixed service liveness response."""

    return {"status": "ok", "service": settings.APP_NAME}
