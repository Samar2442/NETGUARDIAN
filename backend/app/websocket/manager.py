from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger("netguardian.ws")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[WS] Client connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"[WS] Client disconnected. Active: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        data_text = json.dumps(message)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(data_text)
            except Exception as e:
                logger.warning(f"[WS] Failed to send to client: {e}")
                self.disconnect(connection)

ws_manager = ConnectionManager()
