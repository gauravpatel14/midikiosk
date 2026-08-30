"""FastAPI Router for MediKiosk Dialogue Manager (Structured History Taking)."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

try:
    from services.dialogue.dialogue_manager import DialogueManager
except ImportError:
    from ..services.dialogue.dialogue_manager import DialogueManager

router = APIRouter(prefix="/dialogue", tags=["Clinical Dialogue Engine"])

# In-memory active dialogue session registry
active_dialogues: Dict[str, DialogueManager] = {}


class DialogueStartRequest(BaseModel):
    session_id: str = Field(..., description="Unique kiosk session UUID")
    language: str = Field(default="hi", description="'hi', 'en', or 'ta'")
    mode: str = Field(default="ALLOPATHIC", description="'ALLOPATHIC' or 'AYUSH'")


class TouchOption(BaseModel):
    label: str
    value: str


class DialogueResponse(BaseModel):
    session_id: str
    current_state: str
    question: str
    options: List[TouchOption]
    is_final: bool
    red_flag_triggered: bool
    red_flag_details: Optional[Dict[str, Any]] = None
    collected_data: Optional[Dict[str, Any]] = None


class DialogueNextRequest(BaseModel):
    session_id: str
    current_state: str
    user_response: str


@router.post("/start", response_model=DialogueResponse, summary="Start Clinical Dialogue")
def start_dialogue_session(payload: DialogueStartRequest) -> DialogueResponse:
    """Initialize structured clinical history interview starting with open-ended complaint."""
    dm = DialogueManager(language=payload.language, mode=payload.mode)
    active_dialogues[payload.session_id] = dm

    q_text, opts, is_final = dm.start_interview()
    return DialogueResponse(
        session_id=payload.session_id,
        current_state=dm.current_state,
        question=q_text,
        options=[TouchOption(**o) for o in opts],
        is_final=is_final,
        red_flag_triggered=dm.red_flag_triggered,
        red_flag_details=dm.red_flag_details,
        collected_data=dm.collected_data,
    )


@router.post("/next", response_model=DialogueResponse, summary="Advance Dialogue State Machine")
async def advance_dialogue_state(payload: DialogueNextRequest) -> DialogueResponse:
    """Process user input (voice text or touch option) and transition to next clinical question."""
    dm = active_dialogues.get(payload.session_id)
    if not dm:
        # Reconstruct session if not in memory
        dm = DialogueManager(language="hi", mode="ALLOPATHIC")
        active_dialogues[payload.session_id] = dm

    q_text, opts, is_final = dm.get_next_question(
        current_state=payload.current_state, user_response=payload.user_response
    )

    if dm.red_flag_triggered:
        from backend.services.websocket_manager import ws_manager
        await ws_manager.broadcast_alert(
            patient_id=payload.session_id,
            kiosk_id="KIOSK-OPD-01",
            red_flag_type=dm.red_flag_details.get("category", "EMERGENCY") if dm.red_flag_details else "EMERGENCY",
            urgency_level="CRITICAL",
            details=dm.red_flag_details,
        )

    return DialogueResponse(
        session_id=payload.session_id,
        current_state=dm.current_state,
        question=q_text,
        options=[TouchOption(**o) for o in opts],
        is_final=is_final,
        red_flag_triggered=dm.red_flag_triggered,
        red_flag_details=dm.red_flag_details,
        collected_data=dm.collected_data,
    )
