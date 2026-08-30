"""Test WebSocket Authentication and Role Authorization for /ws/triage."""

import pytest
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient

from backend.main import app
from backend.security import create_access_token
from backend.services.websocket_manager import ws_manager

client = TestClient(app)


def test_websocket_connection_without_token():
    """Connecting without token must close with code 4401."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/triage"):
            pass
    assert exc_info.value.code == 4401


def test_websocket_connection_invalid_token():
    """Connecting with malformed or invalid token must close with code 4401."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/triage?token=invalid.jwt.token"):
            pass
    assert exc_info.value.code == 4401


def test_websocket_connection_unauthorized_role():
    """Connecting with valid token but non-triage role (e.g., patient, clerk) must close with code 4403."""
    patient_token = create_access_token("patient-001", role="patient")
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/triage?token={patient_token}"):
            pass
    assert exc_info.value.code == 4403

    clerk_token = create_access_token("clerk-001", role="clerk")
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/triage?token={clerk_token}"):
            pass
    assert exc_info.value.code == 4403


def test_websocket_connection_authorized_triage_staff():
    """Valid triage_staff token in query string connects successfully and receives ping/pong."""
    staff_token = create_access_token("staff-user-123", role="triage_staff")
    with client.websocket_connect(f"/ws/triage?token={staff_token}") as ws:
        ws.send_text("ping")
        resp = ws.receive_text()
        assert resp == "pong"


def test_websocket_connection_authorized_admin():
    """Valid admin token in query string connects successfully."""
    admin_token = create_access_token("admin-user-001", role="admin")
    with client.websocket_connect(f"/ws/triage?token={admin_token}") as ws:
        ws.send_text("ping")
        resp = ws.receive_text()
        assert resp == "pong"


def test_websocket_connection_via_authorization_header():
    """Valid token in Authorization header connects successfully."""
    staff_token = create_access_token("staff-user-456", role="triage_staff")
    headers = {"Authorization": f"Bearer {staff_token}"}
    with client.websocket_connect("/ws/triage", headers=headers) as ws:
        ws.send_text("ping")
        resp = ws.receive_text()
        assert resp == "pong"
