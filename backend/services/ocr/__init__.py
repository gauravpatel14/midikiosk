"""MediKiosk document digitisation and OCR package."""

from backend.services.ocr.document_ocr import DocumentOCR, document_ocr
from backend.services.ocr.engines import (
    EasyOCREngine,
    OCREngineResult,
    PaddleOCREngine,
    TesseractEngine,
    get_ocr_engine,
)
from backend.services.ocr.handwriting import HandwritingRecogniser, handwriting_model
from backend.services.ocr.preprocess import (
    PreprocessResult,
    deskew_image,
    denoise_image,
    preprocess_for_ocr,
)

#: Historical alias.
HandwrittenPrescriptionModelStub = HandwritingRecogniser

__all__ = [
    "DocumentOCR",
    "document_ocr",
    "OCREngineResult",
    "PaddleOCREngine",
    "EasyOCREngine",
    "TesseractEngine",
    "get_ocr_engine",
    "HandwritingRecogniser",
    "HandwrittenPrescriptionModelStub",
    "handwriting_model",
    "preprocess_for_ocr",
    "deskew_image",
    "denoise_image",
    "PreprocessResult",
]
