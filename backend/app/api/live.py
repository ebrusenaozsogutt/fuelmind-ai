"""WebSocket access to station-scoped live simulation messages."""

from __future__ import annotations

import logging
import asyncio
import json
from datetime import datetime

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.database import get_db
from app.live.connection_manager import ConnectionManager
from app.simulation.manager import SimulationManager
from app.repositories.station_repository import StationRepository
from app.utils.datetime_utils import utc_now
from app.config import settings
from app.api.dependencies import require_operator_or_admin
from app.models.user import User
from app.schemas.live_data import LiveStatusRead, SensorHistoryRead
from app.services.live_history_service import LiveHistoryService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live"])


def _history_filters(from_time: Annotated[datetime | None, Query(alias="from")] = None, to_time: Annotated[datetime | None, Query(alias="to")] = None, limit: Annotated[int, Query(ge=1, le=5000)] = 600) -> dict[str, object]:
    return LiveHistoryService.filters(from_time, to_time, limit)


@router.get("/stations/{station_id}/sensor-history", response_model=list[SensorHistoryRead])
def station_sensor_history(station_id: int, filters: Annotated[dict[str, object], Depends(_history_filters)], db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)]):
    return LiveHistoryService(db).station_history(station_id, **filters)


@router.get("/tanks/{tank_id}/sensor-history", response_model=list[SensorHistoryRead])
def tank_sensor_history(tank_id: int, filters: Annotated[dict[str, object], Depends(_history_filters)], db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)]):
    return LiveHistoryService(db).tank_history(tank_id, **filters)


@router.get("/pumps/{pump_id}/sensor-history", response_model=list[SensorHistoryRead])
def pump_sensor_history(pump_id: int, filters: Annotated[dict[str, object], Depends(_history_filters)], db: Annotated[Session, Depends(get_db)], _: Annotated[User, Depends(require_operator_or_admin)]):
    return LiveHistoryService(db).pump_history(pump_id, **filters)


@router.get("/stations/{station_id}/live-status", response_model=LiveStatusRead)
def station_live_status(
    station_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_operator_or_admin)],
):
    """Return only the process-owned realtime run's live snapshot.

    Historical readings are intentionally retained in the database, but they
    are not runtime state.  A new run gets a fresh clock and sequence starting
    at one, so selecting the manager's active run prevents old packets from
    being shown as the new run's current status.
    """
    manager: SimulationManager | None = getattr(
        request.app.state, "simulation_manager", None
    )
    run_id = manager.active_run_id_for_station(station_id) if manager else None
    return LiveHistoryService(db).status(station_id, simulation_run_id=run_id)


async def _heartbeat(manager: ConnectionManager, station_id: int, websocket: WebSocket) -> None:
    interval = settings.LIVE_WS_HEARTBEAT_SECONDS
    while True:
        await asyncio.sleep(interval)
        if manager.is_stale(websocket, interval * 2):
            # Do not leave a stale socket registered while its receive loop is
            # waiting for the close frame to be processed by the ASGI server.
            # ``disconnect`` is idempotent, so the endpoint's ``finally`` block
            # can safely perform the normal cleanup afterwards too.
            await manager.disconnect(station_id, websocket)
            await websocket.close(code=1001)
            return
        try:
            await manager.send_json(websocket, {"event_type": "ping", "generated_at": utc_now().isoformat()})
        except Exception:
            logger.debug("Live heartbeat send failed: station_id=%s", station_id)
            await manager.disconnect(station_id, websocket)
            return


def _station_exists(station_id: int) -> bool:
    session = SessionLocal()
    try:
        return StationRepository(session).get(station_id) is not None
    finally:
        session.close()


@router.websocket("/ws/stations/{station_id}/live")
async def station_live_websocket(websocket: WebSocket, station_id: int) -> None:
    """Register one client on a station channel until it disconnects."""

    if not _station_exists(station_id):
        await websocket.close(code=1008)
        return
    manager: ConnectionManager = websocket.app.state.connection_manager
    connected = False
    heartbeat_task: asyncio.Task[None] | None = None
    try:
        await manager.connect(station_id, websocket)
        connected = True
        await websocket.send_json(
            {
                "event_type": "connection_ready",
                "station_id": station_id,
                "generated_at": utc_now().isoformat(),
            }
        )
        heartbeat_task = asyncio.create_task(_heartbeat(manager, station_id, websocket))
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text"):
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and payload.get("event_type") == "pong":
                    manager.mark_pong(websocket)
    except WebSocketDisconnect:
        logger.debug("Live WebSocket disconnected: station_id=%s", station_id)
    except Exception:
        logger.exception("Live WebSocket failed: station_id=%s", station_id)
        if connected:
            try:
                await websocket.close(code=1011)
            except RuntimeError:
                pass
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)
        if connected:
            await manager.disconnect(station_id, websocket)
