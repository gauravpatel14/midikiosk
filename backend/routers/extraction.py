"""FastAPI Router for Clinical Entity Extraction from OCR/Transcription text."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

try:
    from services.extraction.entity_extractor import EntityExtractor
except ImportError:
    from ..services.extraction.entity_extractor import EntityExtractor

router = APIRouter(prefix="/nlp", tags=["Clinical NLP & Entity Extraction"])
extractor = EntityExtractor()


class EntityExtractRequest(BaseModel):
    text: str = Field(..., description="Unstructured medical text from OCR scan or voice interview")
    use_llm: bool = Field(default=True, description="Whether to leverage LLM for contextual parsing")


class EntityExtractResponse(BaseModel):
    status: str
    extraction_method: str
    overall_confidence: float
    entities: Dict[str, Any]
    raw_text_length: int


@router.post("/extract-entities", response_model=EntityExtractResponse, summary="Extract Clinical Entities")
def extract_clinical_entities_endpoint(payload: EntityExtractRequest) -> EntityExtractResponse:
    """Extract diagnoses (ICD-10), medications, lab results, procedures, allergies, and dates."""
    result = extractor.extract(payload.text)
    return EntityExtractResponse(**result)


# ==============================================================================
# Drug Interaction Detection
# ==============================================================================

class DrugInteractionRequest(BaseModel):
    medications: List[str] = Field(..., description="List of medication names to evaluate pairwise")


class DrugInteractionItem(BaseModel):
    drug_a: str
    drug_b: str
    severity: str
    description: str
    source: str


class DrugInteractionResponse(BaseModel):
    status: str
    medications_checked: int
    interactions_count: int
    interactions: List[DrugInteractionItem]


@router.post("/check-interactions", response_model=DrugInteractionResponse, summary="Check Drug Interactions")
async def check_drug_interactions_endpoint(payload: DrugInteractionRequest) -> DrugInteractionResponse:
    """Evaluate pairwise drug interactions using real NIH RxNav or DrugBank clinical data."""
    from backend.services.drug_interaction import drug_interaction_service
    interactions = await drug_interaction_service.check_interactions_async(payload.medications)
    return DrugInteractionResponse(
        status="success",
        medications_checked=len(payload.medications),
        interactions_count=len(interactions),
        interactions=[DrugInteractionItem(**item) for item in interactions],
    )
