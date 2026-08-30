"""FastAPI Router for Hospital Information System (HIS) Integration."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

try:
    from services.his.service import his_service
except ImportError:
    from ..services.his.service import his_service

router = APIRouter(prefix="/his", tags=["HIS EMR Integration"])


class HISSummarySendRequest(BaseModel):
    patient_id: str = Field(..., description="Patient ID or ABHA ID")
    summary: Dict[str, Any] = Field(..., description="Clinical history & physician summary note")
    documents: Optional[List[Dict[str, Any]]] = Field(default=None, description="Scanned prescriptions & lab reports")
    adapter_override: Optional[str] = Field(default=None, description="Optional adapter override (fhir, hl7v2, webhook, mock)")


class HISSwitchAdapterRequest(BaseModel):
    adapter: str = Field(..., description="Adapter name: fhir, hl7v2, webhook, mock")


@router.post("/send-summary", summary="Send Summary to Hospital HIS")
def send_summary_to_his_endpoint(
    payload: HISSummarySendRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """Dispatch clinical summary to the hospital EMR system via configured protocol."""
    if payload.adapter_override:
        his_service.set_adapter(payload.adapter_override)

    res = his_service.send_summary(payload.patient_id, payload.summary, payload.documents)

    if background_tasks and payload.documents:
        doc_paths = [d.get("file_location") or d.get("file_path") for d in payload.documents if d.get("file_location") or d.get("file_path")]
        if doc_paths:
            from backend.services.cleanup import cleanup_session_temp_files
            background_tasks.add_task(cleanup_session_temp_files, doc_paths)

    return res


@router.post("/adapter/switch", summary="Switch Active HIS Adapter")
def switch_his_adapter_endpoint(payload: HISSwitchAdapterRequest) -> Dict[str, Any]:
    """Dynamically switch active HIS adapter protocol."""
    his_service.set_adapter(payload.adapter)
    return {
        "status": "success",
        "active_adapter": his_service.active_adapter_name,
        "message": f"Active HIS adapter switched to '{payload.adapter}'",
    }


@router.get("/status", summary="Get HIS Adapter Status")
def get_his_status_endpoint() -> Dict[str, Any]:
    """Return active HIS adapter configuration and state."""
    return {
        "status": "online",
        "active_adapter": his_service.active_adapter_name,
        "supported_protocols": ["FHIR_R4", "HL7_v2.5", "WEBHOOK", "MOCK"],
    }
