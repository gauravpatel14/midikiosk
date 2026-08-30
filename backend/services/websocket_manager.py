"""WebSocket Connection Manager for Real-Time Triage & Emergency Alert Broadcasting."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

from backend.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages active staff dashboard WebSocket connections for instant clinical triage alerts."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, user_id: Optional[str] = None, role: Optional[str] = None
    ) -> None:
        """Accept WebSocket handshake and register client connection with user metadata."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
            self.connection_metadata[websocket] = {
                "user_id": user_id,
                "role": role,
                "connected_at": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(
            "triage_ws_client_connected",
            total_connected=len(self.active_connections),
            user_id=user_id,
            role=role,
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister closed WebSocket connection and clean up metadata."""
        async with self._lock:
            self.active_connections.discard(websocket)
            self.connection_metadata.pop(websocket, None)
        logger.info("triage_ws_client_disconnected", total_connected=len(self.active_connections))

    async def broadcast_alert(
        self,
        patient_id: str,
        kiosk_id: str,
        red_flag_type: str,
        urgency_level: str = "CRITICAL",
        details: Any = None,
    ) -> None:
        """Send JSON emergency alert to all connected staff dashboard clients."""
        payload: Dict[str, Any] = {
            "event": "EMERGENCY_TRIAGE_ALERT",
            "patient_id": str(patient_id),
            "kiosk_id": str(kiosk_id),
            "red_flag_type": red_flag_type,
            "urgency_level": urgency_level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }

        async with self._lock:
            dead_connections: List[WebSocket] = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(payload)
                except Exception as exc:
                    logger.warning("triage_ws_send_failed", error=str(exc))
                    dead_connections.append(connection)

            for dead in dead_connections:
                self.active_connections.discard(dead)

        logger.info(
            "triage_alert_broadcasted",
            patient_id=patient_id,
            kiosk_id=kiosk_id,
            flag=red_flag_type,
            recipients=len(self.active_connections),
        )


ws_manager = ConnectionManager()
