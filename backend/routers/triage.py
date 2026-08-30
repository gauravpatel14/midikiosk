"""FastAPI Router for Emergency Red Flag Triage Checking."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    from services.triage.red_flag_detector import red_flag_detector
except ImportError:
    from ..services.triage.red_flag_detector import red_flag_detector

router = APIRouter(prefix="/triage", tags=["Emergency Triage & Red Flags"])


class RedFlagCheckRequest(BaseModel):
    text: Optional[str] = Field(default=None, description="Patient voice transcript or selected touch chip")
    vitals: Optional[Dict[str, Any]] = Field(default=None, description="Physiological vitals (e.g. systolic_bp, spo2, heart_rate)")


class RedFlagCheckResponse(BaseModel):
    is_flagged: bool
    flags_count: int
    flags: List[Dict[str, Any]]


@router.post("/check-flags", response_model=RedFlagCheckResponse, summary="Check Red Flags in Text and Vitals")
async def check_red_flags_endpoint(payload: RedFlagCheckRequest) -> RedFlagCheckResponse:
    """Evaluate text and vitals against emergency red-flag patterns and clinical thresholds."""
    from backend.services.websocket_manager import ws_manager
    is_flagged, flags = red_flag_detector.has_red_flags(payload.text, payload.vitals)
    if is_flagged:
        for flag in flags:
            await ws_manager.broadcast_alert(
                patient_id="walk_in_triage",
                kiosk_id="KIOSK-TRIAGE-01",
                red_flag_type=flag.get("category", "EMERGENCY"),
                urgency_level=flag.get("severity", "CRITICAL"),
                details=flag,
            )
    return RedFlagCheckResponse(
        is_flagged=is_flagged,
        flags_count=len(flags),
        flags=flags,
    )
