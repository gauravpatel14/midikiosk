"""FastAPI Router for Clinical Summary Generation."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

try:
    from services.summary.summary_generator import SummaryGenerator
except ImportError:
    from ..services.summary.summary_generator import SummaryGenerator

router = APIRouter(prefix="/summary", tags=["Clinical Summary Generation"])
summary_gen = SummaryGenerator()


class SummaryGenerateRequest(BaseModel):
    patient_data: Dict[str, Any] = Field(..., description="Patient demographics & dialogue manager state")
    document_data: Optional[Dict[str, Any]] = Field(default=None, description="OCR extracted laboratory and prescription entities")


class SummaryGenerateResponse(BaseModel):
    status: str
    html_summary: str
    plain_text_summary: str
    generated_at: str


@router.post("/generate", response_model=SummaryGenerateResponse, summary="Generate Clinical Summary")
def generate_clinical_summary_endpoint(
    payload: SummaryGenerateRequest,
    background_tasks: BackgroundTasks,
) -> SummaryGenerateResponse:
    """Compile structured history and OCR lab/medication extractions into physician HTML and text summary."""
    html_out, text_out = summary_gen.generate(payload.patient_data, payload.document_data)

    if background_tasks and payload.document_data:
        p = payload.document_data.get("file_location") or payload.document_data.get("file_path")
        if p:
            from backend.services.cleanup import cleanup_session_temp_files
            background_tasks.add_task(cleanup_session_temp_files, [p])

    return SummaryGenerateResponse(
        status="success",
        html_summary=html_out,
        plain_text_summary=text_out,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
