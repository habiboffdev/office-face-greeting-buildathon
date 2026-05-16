import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._display_clients: list[WebSocket] = []

    async def connect_display(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._display_clients.append(websocket)
        logger.info("Display WS connected (%d clients)", len(self._display_clients))

    def disconnect_display(self, websocket: WebSocket) -> None:
        if websocket in self._display_clients:
            self._display_clients.remove(websocket)
        logger.info("Display WS disconnected (%d clients)", len(self._display_clients))

    async def broadcast_welcome(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        message = json.dumps({"type": "welcome", **payload})
        for ws in self._display_clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_display(ws)
