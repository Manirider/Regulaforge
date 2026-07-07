from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from regulaforge.common.utils import create_response

logger = logging.getLogger(__name__)


class WebSocketEvent(str, Enum):
    NOTIFICATION = "notification"
    AGENT_STATUS = "agent_status"
    CONTRACT_UPDATE = "contract_update"
    REGULATION_UPDATE = "regulation_update"
    REPORT_READY = "report_ready"
    ASSESSMENT_COMPLETE = "assessment_complete"
    SYSTEM_ALERT = "system_alert"


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._user_connections: dict[str, set[WebSocket]] = {}
        self._handlers: dict[str, list[Callable]] = {}

    async def connect(self, websocket: WebSocket, tenant_id: str = "", user_id: str = "") -> None:
        await websocket.accept()
        if tenant_id:
            self._connections.setdefault(tenant_id, set()).add(websocket)
        if user_id:
            self._user_connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, websocket: WebSocket, tenant_id: str = "", user_id: str = "") -> None:
        if tenant_id and tenant_id in self._connections:
            self._connections[tenant_id].discard(websocket)
            if not self._connections[tenant_id]:
                del self._connections[tenant_id]
        if user_id and user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

    async def broadcast_to_tenant(
        self, tenant_id: str, event: WebSocketEvent, data: dict[str, Any],
    ) -> None:
        payload = json.dumps({
            "event": event.value,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        })
        connections = self._connections.get(tenant_id, set())
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections.discard(ws)

    async def send_to_user(
        self, user_id: str, event: WebSocketEvent, data: dict[str, Any],
    ) -> None:
        payload = json.dumps({
            "event": event.value,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        })
        connections = self._user_connections.get(user_id, set())
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections.discard(ws)

    async def broadcast(self, event: WebSocketEvent, data: dict[str, Any]) -> None:
        payload = json.dumps({
            "event": event.value,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        })
        for tenant_id, connections in list(self._connections.items()):
            dead: list[WebSocket] = []
            for ws in connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                connections.discard(ws)

    def register_handler(self, event: str, handler: Callable) -> None:
        self._handlers.setdefault(event, []).append(handler)

    @property
    def active_connections(self) -> int:
        total = sum(len(c) for c in self._connections.values())
        total += sum(len(c) for c in self._user_connections.values())
        return total


manager = ConnectionManager()


def create_websocket_router() -> APIRouter:
    router = APIRouter(prefix="/ws", tags=["WebSocket"])

    @router.websocket("/{tenant_id}")
    async def tenant_websocket(websocket: WebSocket, tenant_id: str, user_id: str = "") -> None:
        await manager.connect(websocket, tenant_id, user_id)
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    event_type = msg.get("event", "")
                    if event_type in manager._handlers:
                        for handler in manager._handlers[event_type]:
                            await handler(websocket, msg.get("data", {}))
                except json.JSONDecodeError:
                    logger.warning("Invalid WebSocket message: %s", data)
        except WebSocketDisconnect:
            await manager.disconnect(websocket, tenant_id, user_id)

    @router.get("/status")
    async def websocket_status() -> dict[str, Any]:
        return create_response(data={
            "active_connections": manager.active_connections,
            "tenants": len(manager._connections),
        })

    return router
