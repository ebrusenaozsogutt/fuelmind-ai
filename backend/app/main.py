"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.alarms import router as alarms_router
from app.api.deliveries import router as deliveries_router
from app.api.dashboard import router as dashboard_router
from app.api.error_handlers import register_exception_handlers
from app.api.fuel_types import router as fuel_types_router
from app.api.live import router as live_router
from app.api.pumps import router as pumps_router
from app.api.sales import router as sales_router
from app.api.simulations import router as simulations_router
from app.api.stations import router as stations_router
from app.api.tanks import router as tanks_router
from app.api.users import router as users_router
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
app.include_router(alarms_router, prefix=settings.API_PREFIX)
app.include_router(fuel_types_router, prefix=settings.API_PREFIX)
app.include_router(stations_router, prefix=settings.API_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_PREFIX)
app.include_router(tanks_router, prefix=settings.API_PREFIX)
app.include_router(pumps_router, prefix=settings.API_PREFIX)
app.include_router(users_router, prefix=settings.API_PREFIX)
app.include_router(sales_router, prefix=settings.API_PREFIX)
app.include_router(deliveries_router, prefix=settings.API_PREFIX)
app.include_router(simulations_router, prefix=settings.API_PREFIX)
app.include_router(live_router, prefix=settings.API_PREFIX)


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
