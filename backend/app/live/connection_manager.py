"""Station-scoped WebSocket connection ownership."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any
from app.utils.datetime_utils import utc_now

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Maintain isolated, in-process WebSocket channels for each station."""

    def __init__(self) -> None:
        self._channels: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._last_pong: dict[WebSocket, object] = {}
        self._send_locks: dict[WebSocket, asyncio.Lock] = {}

    async def connect(self, station_id: int, websocket: WebSocket) -> None:
        """Accept and register a connection in its station's channel."""

        await websocket.accept()
        async with self._lock:
            channel = self._channels.setdefault(station_id, set())
            channel.add(websocket)
            self._last_pong[websocket] = utc_now()
            self._send_locks[websocket] = asyncio.Lock()
            count = len(channel)
        logger.info("WebSocket connected: station_id=%s connections=%s", station_id, count)

    async def disconnect(self, station_id: int, websocket: WebSocket) -> None:
        """Idempotently remove a connection and clean up an empty channel."""

        async with self._lock:
            channel = self._channels.get(station_id)
            if channel is None:
                return
            channel.discard(websocket)
            self._last_pong.pop(websocket, None)
            self._send_locks.pop(websocket, None)
            count = len(channel)
            if not channel:
                self._channels.pop(station_id, None)
                logger.info("Station WebSocket channel cleaned: station_id=%s", station_id)
        logger.info("WebSocket disconnected: station_id=%s connections=%s", station_id, count)

    async def broadcast(self, station_id: int, message: Mapping[str, Any]) -> None:
        """Send a JSON-compatible message to one station without cross-channel leaks."""

        async with self._lock:
            recipients = tuple(self._channels.get(station_id, ()))
        failed: list[WebSocket] = []
        for websocket in recipients:
            try:
                await self.send_json(websocket, message)
            except Exception:
                failed.append(websocket)
                logger.warning("WebSocket send failure: station_id=%s", station_id)
        for websocket in failed:
            await self.disconnect(station_id, websocket)

    def connection_count(self, station_id: int) -> int:
        """Return a snapshot count for one station channel."""

        return len(self._channels.get(station_id, ()))

    def total_connection_count(self) -> int:
        """Return the number of currently registered connections."""

        return sum(len(channel) for channel in self._channels.values())

    def has_connections(self, station_id: int) -> bool:
        """Return whether the station currently has at least one connection."""

        return self.connection_count(station_id) > 0

    async def send_json(self, websocket: WebSocket, message: Mapping[str, Any]) -> None:
        """Serialize sends per connection while leaving collection locks free."""

        lock = self._send_locks.get(websocket)
        if lock is None:
            raise RuntimeError("WebSocket is not registered.")
        async with lock:
            await websocket.send_json(dict(message))

    def mark_pong(self, websocket: WebSocket) -> None:
        """Record a server-side liveness acknowledgement for a registered client."""

        if websocket in self._last_pong:
            self._last_pong[websocket] = utc_now()

    def is_stale(self, websocket: WebSocket, timeout_seconds: float) -> bool:
        """Return whether a client has missed the supplied pong timeout."""

        timestamp = self._last_pong.get(websocket)
        return timestamp is None or (utc_now() - timestamp).total_seconds() > timeout_seconds
