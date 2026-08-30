"""FastAPI main application for MediKiosk backend.

Provides REST and WebSocket endpoints for Kiosks, HIS integration,
ABDM consent validation, ASR/TTS speech engines, Dialogue State Machine,
Document Processing OCR, Clinical NLP Extraction, Summary Generation,
ABDM FHIR R4 Health Information Exchange, and emergency triage nurse alerting.
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from typing import Any, Dict, List
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

try:
    import backend.models
    import backend.database
    sys.modules.setdefault("models", backend.models)
    sys.modules.setdefault("database", backend.database)

    from backend.database import get_db, init_db
    from backend.models import HistorySession, Patient, RedFlag, Summary, User
    from backend.routers.auth import router as auth_router
    from backend.routers.dialogue import router as dialogue_router
    from backend.routers.extraction import router as extraction_router
    from backend.routers.fhir import router as fhir_router
    from backend.routers.his import router as his_router
    from backend.routers.ocr import router as ocr_router
    from backend.routers.speech import router as speech_router
    from backend.routers.summary import router as summary_router
    from backend.routers.triage import router as triage_router
except ImportError:
    from database import get_db, init_db
    from models import HistorySession, Patient, RedFlag, Summary, User
    from routers.auth import router as auth_router
    from routers.dialogue import router as dialogue_router
    from routers.extraction import router as extraction_router
    from routers.fhir import router as fhir_router
    from routers.his import router as his_router
    from routers.ocr import router as ocr_router
    from routers.speech import router as speech_router
    from routers.summary import router as summary_router
    from routers.triage import router as triage_router

from contextlib import asynccontextmanager
from fastapi import Query, WebSocket, WebSocketDisconnect

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: Validate clinical data files authenticity & integrity
    from backend.services.data_validator import validate_all_data_files
    validate_all_data_files()

    # 2. Startup: Launch cleanup scheduler with cross-worker distributed lock
    from backend.services.cleanup import start_cleanup_scheduler, stop_cleanup_scheduler
    start_cleanup_scheduler()
    yield
    # Shutdown: Stop scheduler and release distributed lock
    stop_cleanup_scheduler()

app = FastAPI(
    title="MediKiosk Clinical History API",
    description="AI-Powered Clinical History Software Platform for All India Institute of Ayurveda & ABDM",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS enabled for Kiosk touchscreens and hospital HIS clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth_router)
app.include_router(speech_router)
app.include_router(dialogue_router)
app.include_router(ocr_router)
app.include_router(extraction_router)
app.include_router(summary_router)
app.include_router(fhir_router)
app.include_router(triage_router)
app.include_router(his_router)


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, Any]:
    """Health check endpoint for kiosk heartbeat monitoring."""
    from backend.services.data_validator import get_data_integrity_status
    return {
        "status": "ok",
        "platform": "MediKiosk",
        "version": "1.0.0",
        "data_integrity": get_data_integrity_status(),
    }


@app.get("/api/v1/sessions/active", tags=["Kiosk Sessions"])
def list_active_sessions(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return active kiosk sessions."""
    sessions = db.query(HistorySession).filter(
        HistorySession.status == "IN_PROGRESS"
    ).all()
    return [
        {
            "id": str(s.id),
            "kiosk_id": s.kiosk_id,
            "patient_id": str(s.patient_id),
            "mode": s.mode.value,
            "language": s.interaction_language,
            "started_at": s.started_at.isoformat(),
        }
        for s in sessions
    ]


@app.get("/api/v1/triage/red-flags", tags=["Triage Emergency"])
def get_unacknowledged_red_flags(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Emergency triage alerts for active red flags."""
    flags = db.query(RedFlag).filter(
        RedFlag.triage_acknowledged_at.is_(None)
    ).order_by(RedFlag.triage_notified_at.desc()).all()
    return [
        {
            "id": str(f.id),
            "session_id": str(f.session_id),
            "patient_id": str(f.patient_id),
            "category": f.flag_category,
            "severity": f.severity_level.value,
            "rule": f.triggered_rule,
            "notified_at": f.triage_notified_at.isoformat(),
        }
        for f in flags
    ]


@app.post("/api/v1/triage/red-flags/{alert_id}/acknowledge", tags=["Triage Emergency"])
def acknowledge_red_flag_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Mark an emergency triage red-flag alert as delivered and acknowledged by staff."""
    flag = db.query(RedFlag).filter(RedFlag.id == alert_id).first()
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Red flag alert {alert_id} not found.",
        )
    now = datetime.now(timezone.utc)
    flag.triage_acknowledged_at = now
    db.commit()
    return {
        "status": "success",
        "alert_id": str(alert_id),
        "acknowledged_at": now.isoformat(),
        "message": "Emergency alert marked as delivered and acknowledged by triage staff.",
    }


@app.websocket("/ws/triage")
async def triage_websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time WebSocket connection for staff dashboard emergency alerts with JWT authentication."""
    # 1. Extract token from query parameter or Authorization header
    raw_token = websocket.query_params.get("token")
    if not raw_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:].strip()
        elif auth_header:
            raw_token = auth_header.strip()

    if not raw_token:
        await websocket.close(code=4401)
        return

    # 2. Validate token
    try:
        from backend.security import decode_token
        payload = decode_token(raw_token)
    except Exception:
        await websocket.close(code=4401)
        return

    # 3. Verify user role: triage_staff or admin
    role = str(payload.get("role") or "").lower()
    user_id = str(payload.get("sub") or "")
    if role not in {"triage_staff", "admin"}:
        await websocket.close(code=4403)
        return

    # 4. Accept connection and store metadata
    from backend.services.websocket_manager import ws_manager
    await ws_manager.connect(websocket, user_id=user_id, role=role)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
