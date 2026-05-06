from __future__ import annotations

import asyncio
from collections import defaultdict
from threading import Lock
from typing import Any

from fastapi import WebSocket

from .models import now_iso


class RealtimeHub:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._job_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._event_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect_job(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._lock:
            self._job_connections[job_id].add(websocket)

    async def disconnect_job(self, job_id: str, websocket: WebSocket) -> None:
        await self._disconnect(self._job_connections, job_id, websocket)

    async def connect_events(self, scope: str, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._lock:
            self._event_connections[scope].add(websocket)

    async def disconnect_events(self, scope: str, websocket: WebSocket) -> None:
        await self._disconnect(self._event_connections, scope, websocket)

    def publish_job(self, job_id: str, message_type: str, payload: dict[str, Any]) -> None:
        self._schedule(
            self._broadcast_to_group(
                self._job_connections,
                job_id,
                self._envelope(message_type, job_id=job_id, scope="job", payload=payload),
            )
        )

    def publish_events(self, scope: str, payload: dict[str, Any]) -> None:
        self._schedule(
            self._broadcast_to_group(
                self._event_connections,
                scope,
                self._envelope("events.updated", scope=scope, payload=payload),
            )
        )

    async def _disconnect(self, mapping: dict[str, set[WebSocket]], key: str, websocket: WebSocket) -> None:
        with self._lock:
            sockets = mapping.get(key)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                mapping.pop(key, None)

    async def _broadcast_to_group(
        self,
        mapping: dict[str, set[WebSocket]],
        key: str,
        message: dict[str, Any],
    ) -> None:
        with self._lock:
            sockets = list(mapping.get(key, set()))
        if not sockets:
            return
        stale: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        if stale:
            with self._lock:
                current = mapping.get(key, set())
                for websocket in stale:
                    current.discard(websocket)
                if not current:
                    mapping.pop(key, None)

    def _schedule(self, coroutine: Any) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    @staticmethod
    def _envelope(
        message_type: str,
        *,
        job_id: str = "",
        scope: str = "",
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": message_type,
            "job_id": job_id,
            "scope": scope,
            "timestamp": now_iso(),
            "payload": payload,
        }
