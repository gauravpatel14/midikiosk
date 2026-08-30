"""FastAPI Router for Document Scanning and Multilingual OCR."""

import os
import shutil
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

try:
    from services.ocr.document_ocr import DocumentOCR
except ImportError:
    from ..services.ocr.document_ocr import DocumentOCR

router = APIRouter(prefix="/documents", tags=["Document OCR & Processing"])
ocr_engine = DocumentOCR()


class OCRProcessResponse(BaseModel):
    status: str
    file_path: str
    filename: str
    page_count: int
    raw_text: str
    detected_languages: List[str]
    primary_language: str
    document_type_hint: str
    confidence_score: float
    document_date: Optional[str] = None
    is_handwritten_suspected: bool
    handwriting_extraction: Optional[Dict[str, Any]] = None
    requires_human_review: Optional[bool] = False
    review_reason: Optional[str] = None
    metadata: Dict[str, Any]
    error: Optional[str] = None
    message: Optional[str] = None


@router.post("/ocr/scan", response_model=OCRProcessResponse, summary="Scan Medical Document (OCR)")
async def scan_medical_document(file: UploadFile = File(...)) -> OCRProcessResponse:
    """Upload scanned image (PNG/JPG) or PDF prescription/lab report to extract text and clinical metadata."""
    temp_dir = "/tmp/medikiosk_documents"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Save uploaded file
    unique_name = f"{uuid.uuid4().hex[:8]}_{file.filename or 'doc.pdf'}"
    target_path = os.path.join(temp_dir, unique_name)

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    result = await ocr_engine.process_async(target_path)
    return OCRProcessResponse(**result)
