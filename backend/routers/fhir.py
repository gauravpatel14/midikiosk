"""FastAPI Router for ABDM FHIR R4 Health Data Exchange."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

try:
    from services.fhir.fhir_builder import (
        create_composition,
        create_consent_resource,
        create_document_reference,
        create_fhir_bundle,
        create_patient_resource,
    )
    from services.fhir.fhir_client import fhir_client
except ImportError:
    from ..services.fhir.fhir_builder import (
        create_composition,
        create_consent_resource,
        create_document_reference,
        create_fhir_bundle,
        create_patient_resource,
    )
    from ..services.fhir.fhir_client import fhir_client

router = APIRouter(prefix="/abdm/fhir", tags=["ABDM FHIR R4 Integration"])


class FHIRPushRequest(BaseModel):
    patient_data: Dict[str, Any] = Field(..., description="Patient demographics and ABHA ID")
    history_data: Dict[str, Any] = Field(..., description="Dialogue manager interview data")
    summary_text: str = Field(..., description="Rendered clinical summary text")
    document_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Scanned document OCR metadata")
    file_location: Optional[str] = Field(default=None, description="Local path to prescription scan/PDF")
    consent_data: Optional[Dict[str, Any]] = Field(default=None, description="Patient DPDP consent record")


class FHIRPushResponse(BaseModel):
    status: str
    transaction_id: str
    request_id: str
    patient_abha_id: str
    hip_id: str
    bundle_id: str
    resources_count: int
    bundle: Dict[str, Any]
    dispatched_at: str
    message: str


@router.post("/bundle-and-push", response_model=FHIRPushResponse, summary="Bundle and Push to ABDM")
async def bundle_and_push_to_abdm_endpoint(payload: FHIRPushRequest) -> FHIRPushResponse:
    """Build Patient, Composition, DocumentReference, and Consent FHIR resources, bundle, and push to ABDM."""
    resources = []

    # 1. Patient Resource
    patient_res = create_patient_resource(payload.patient_data)
    resources.append(patient_res)

    # 2. Composition Resource (Clinical OPD Consultation Note)
    comp_res = create_composition(payload.history_data, payload.summary_text)
    resources.append(comp_res)

    # 3. DocumentReference Resource (if scanned document present)
    if payload.document_metadata:
        doc_res = create_document_reference(payload.document_metadata, payload.file_location)
        resources.append(doc_res)

    # 4. Consent Resource (if consent record present)
    if payload.consent_data:
        consent_res = create_consent_resource(payload.consent_data)
        resources.append(consent_res)

    # Extract ABHA identifier
    demo = payload.patient_data.get("demographics", payload.patient_data)
    abha_id = demo.get("abha_id") or demo.get("abha_address") or "unknown_abha"

    result = await fhir_client.push_to_abdm(resources, patient_abha_id=abha_id)
    return FHIRPushResponse(**result)


@router.post("/preview", summary="Preview FHIR R4 Bundle")
def preview_fhir_bundle_endpoint(payload: FHIRPushRequest) -> Dict[str, Any]:
    """Generate and return raw FHIR R4 JSON bundle for review before dispatch."""
    resources = [
        create_patient_resource(payload.patient_data),
        create_composition(payload.history_data, payload.summary_text),
    ]
    if payload.document_metadata:
        resources.append(create_document_reference(payload.document_metadata, payload.file_location))
    if payload.consent_data:
        resources.append(create_consent_resource(payload.consent_data))

    return create_fhir_bundle(resources)
